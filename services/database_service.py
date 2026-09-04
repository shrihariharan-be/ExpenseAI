import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config

class DatabaseService:
    def __init__(self, db_path=None):
        self.db_path = db_path or Config.DATABASE_PATH
        self._ensure_db_dir()

    def _ensure_db_dir(self):
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        try:
            yield conn
        finally:
            conn.close()

    def init_db(self):
        self._ensure_db_dir()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Users Table with role, last_login, and onboarding_completed
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('admin', 'user')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    onboarding_completed INTEGER DEFAULT 0
                )
            ''')

            # 2. Transactions Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    type TEXT NOT NULL CHECK(type IN ('Income', 'Expense')),
                    category TEXT NOT NULL,
                    description TEXT,
                    amount REAL NOT NULL CHECK(amount > 0),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')

            # 3. Budgets Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS budgets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    monthly_budget REAL NOT NULL CHECK(monthly_budget > 0),
                    month_year TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, category, month_year),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')

            # 4. Performance Indexes for fast multi-user lookups and queries
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tx_user_date ON transactions(user_id, date DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tx_user_type_cat ON transactions(user_id, type, category)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_budgets_user_month ON budgets(user_id, month_year)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
            conn.commit()

        self.seed_sample_data()

    # ------------------- USER AUTHENTICATION METHODS ------------------- #

    @staticmethod
    def validate_password_complexity(password):
        """
        Validates password strength:
        - At least 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one number
        """
        if not password or len(password) < 8:
            return False, "Password must be at least 8 characters long."
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter (A-Z)."
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter (a-z)."
        if not re.search(r'\d', password):
            return False, "Password must contain at least one number (0-9)."
        return True, "Strong password"

    def create_user(self, full_name, email, password, role='user', onboarding_completed=0):
        full_name = (full_name or '').strip()
        email = (email or '').strip().lower()

        if len(full_name) < 2:
            raise ValueError("Please provide a valid full name.")
        if '@' not in email or '.' not in email:
            raise ValueError("Please provide a valid email address.")

        is_valid, msg = self.validate_password_complexity(password)
        if not is_valid:
            raise ValueError(msg)

        if role not in ['admin', 'user']:
            role = 'user'

        pwd_hash = generate_password_hash(password)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (full_name, email, password_hash, role, onboarding_completed)
                VALUES (?, ?, ?, ?, ?)
            ''', (full_name, email, pwd_hash, role, onboarding_completed))
            conn.commit()
            return cursor.lastrowid

    def get_user_by_email(self, email):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE LOWER(email) = ?', ((email or '').strip().lower(),))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def verify_user(self, email, password):
        user = self.get_user_by_email(email)
        if user and check_password_hash(user['password_hash'], password):
            # Update last_login timestamp
            self.update_last_login(user['id'])
            user['last_login'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            return user
        return None

    def update_last_login(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?
            ''', (user_id,))
            conn.commit()

    def set_onboarding_completed(self, user_id, completed=1):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET onboarding_completed = ? WHERE id = ?
            ''', (completed, user_id))
            conn.commit()

    def change_user_password(self, user_id, current_password, new_password):
        user = self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User account not found.")

        if not check_password_hash(user['password_hash'], current_password):
            raise ValueError("Current password is incorrect.")

        is_valid, msg = self.validate_password_complexity(new_password)
        if not is_valid:
            raise ValueError(msg)

        new_hash = generate_password_hash(new_password)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, user_id))
            conn.commit()
            return True

    # ------------------- ADMIN PANEL & SYSTEM MANAGEMENT ------------------- #

    def get_all_users_with_stats(self):
        """
        Returns all registered users with their transaction count, total spend,
        joined date, and active status for admin management.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    u.id, u.full_name, u.email, u.role, u.created_at, u.last_login,
                    COUNT(t.id) as transaction_count,
                    COALESCE(SUM(CASE WHEN t.type = 'Expense' THEN t.amount ELSE 0 END), 0.0) as total_expenses,
                    COALESCE(SUM(CASE WHEN t.type = 'Income' THEN t.amount ELSE 0 END), 0.0) as total_income
                FROM users u
                LEFT JOIN transactions t ON u.id = t.user_id
                GROUP BY u.id
                ORDER BY u.created_at DESC
            ''')
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_system_overview_stats(self):
        """
        System-wide statistics for the Admin Panel:
        Total Users, Total Transactions, Total Income, Total Expenses, Active Users (last 30 days).
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Users count
            cursor.execute('SELECT COUNT(*) as count FROM users')
            total_users = cursor.fetchone()['count']

            # Active users (last 30 days)
            cursor.execute('''
                SELECT COUNT(*) as count FROM users 
                WHERE last_login >= datetime('now', '-30 days')
            ''')
            active_users = cursor.fetchone()['count']

            # Transactions KPIs
            cursor.execute('''
                SELECT 
                    COUNT(*) as tx_count,
                    COALESCE(SUM(CASE WHEN type = 'Income' THEN amount ELSE 0 END), 0.0) as total_income,
                    COALESCE(SUM(CASE WHEN type = 'Expense' THEN amount ELSE 0 END), 0.0) as total_expenses
                FROM transactions
            ''')
            tx_row = cursor.fetchone()
            total_tx = tx_row['tx_count']
            total_income = tx_row['total_income']
            total_expenses = tx_row['total_expenses']

            # Recent 5 registrations
            cursor.execute('SELECT id, full_name, email, role, created_at FROM users ORDER BY created_at DESC LIMIT 5')
            recent_users = [dict(r) for r in cursor.fetchall()]

            return {
                'total_users': total_users,
                'active_users': active_users,
                'total_transactions': total_tx,
                'total_income': round(float(total_income), 2),
                'total_expenses': round(float(total_expenses), 2),
                'recent_users': recent_users
            }

    def delete_user_by_admin(self, target_user_id, admin_user_id):
        """
        Safely deletes a user account.
        Prevents deleting self or the primary system admin account.
        """
        if int(target_user_id) == int(admin_user_id):
            raise ValueError("Security violation: You cannot delete your own active administrator account.")

        target = self.get_user_by_id(target_user_id)
        if not target:
            raise ValueError("Target user not found.")

        if target['email'].lower() == Config.ADMIN_EMAIL.lower():
            raise ValueError("The primary system administrator account cannot be deleted.")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM users WHERE id = ?', (target_user_id,))
            conn.commit()
            return cursor.rowcount > 0

    # ------------------- DATA SEEDING ------------------- #

    def seed_sample_data(self):
        # 1. Provision Demo Account first (id = 1) with sample data
        demo_email = 'demo@example.com'
        demo_user = self.get_user_by_email(demo_email)
        if not demo_user:
            demo_id = self.create_user(
                full_name='Demo User',
                email=demo_email,
                password='Demo@123',
                role='user',
                onboarding_completed=1
            )
        else:
            demo_id = demo_user['id']

        # 2. Provision Administrator Account (id = 2)
        admin_email = Config.ADMIN_EMAIL
        admin = self.get_user_by_email(admin_email)
        if not admin:
            self.create_user(
                full_name=Config.ADMIN_NAME,
                email=admin_email,
                password=Config.ADMIN_PASSWORD,
                role='admin',
                onboarding_completed=1
            )

        # 3. Seed demo transactions
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as count FROM transactions WHERE user_id = ?', (demo_id,))
            count = cursor.fetchone()['count']
            if count == 0:
                sample_transactions = [
                    # May 2026
                    (demo_id, '2026-05-01', 'Income', 'Salary', 'Monthly Salary May', 50000.0),
                    (demo_id, '2026-05-03', 'Expense', 'Bills', 'Electricity Bill May', 1450.0),
                    (demo_id, '2026-05-05', 'Expense', 'Food', 'Monthly Grocery Supermarket', 4200.0),
                    (demo_id, '2026-05-08', 'Expense', 'Transportation', 'Monthly Metro Pass', 800.0),
                    (demo_id, '2026-05-12', 'Expense', 'Shopping', 'Summer Clothing Shopping', 3200.0),
                    (demo_id, '2026-05-15', 'Income', 'Freelance', 'UI/UX Design Project', 12000.0),
                    (demo_id, '2026-05-18', 'Expense', 'Entertainment', 'Movie & Dinner with Friends', 1600.0),
                    (demo_id, '2026-05-22', 'Expense', 'Healthcare', 'Dental Checkup & Cleaning', 1200.0),
                    (demo_id, '2026-05-28', 'Expense', 'Education', 'Python & Data Science Course', 2500.0),

                    # June 2026
                    (demo_id, '2026-06-01', 'Income', 'Salary', 'Monthly Salary June', 50000.0),
                    (demo_id, '2026-06-02', 'Expense', 'Bills', 'High Speed WiFi Internet', 999.0),
                    (demo_id, '2026-06-04', 'Expense', 'Food', 'Groceries and Vegetables', 3800.0),
                    (demo_id, '2026-06-07', 'Expense', 'Transportation', 'Petrol for Car', 2000.0),
                    (demo_id, '2026-06-10', 'Income', 'Investment', 'Stock Market Dividends', 2500.0),
                    (demo_id, '2026-06-14', 'Expense', 'Shopping', 'Smartphone Accessories', 1500.0),
                    (demo_id, '2026-06-18', 'Expense', 'Travel', 'Weekend Getaway Resort', 6500.0),
                    (demo_id, '2026-06-22', 'Expense', 'Food', 'Restaurant Family Dinner', 2100.0),
                    (demo_id, '2026-06-27', 'Expense', 'Bills', 'Mobile Phone Postpaid Bill', 699.0),

                    # July 2026
                    (demo_id, '2026-07-01', 'Income', 'Salary', 'Monthly Salary July', 52000.0),
                    (demo_id, '2026-07-03', 'Expense', 'Bills', 'Electricity Bill July', 1850.0),
                    (demo_id, '2026-07-05', 'Income', 'Freelance', 'Backend API Development', 15000.0),
                    (demo_id, '2026-07-08', 'Expense', 'Food', 'Organic Mart Grocery', 4500.0),
                    (demo_id, '2026-07-12', 'Expense', 'Transportation', 'Cab & Auto Rides', 650.0),
                    (demo_id, '2026-07-16', 'Expense', 'Healthcare', 'Routine Health Checkup & Labs', 1800.0),
                    (demo_id, '2026-07-20', 'Expense', 'Entertainment', 'Concert Tickets', 2500.0),
                    (demo_id, '2026-07-24', 'Expense', 'Education', 'Cloud Architecture Books', 1400.0),
                    (demo_id, '2026-07-29', 'Expense', 'Shopping', 'Noise Cancelling Headphones', 4999.0),

                    # August 2026
                    (demo_id, '2026-08-01', 'Income', 'Salary', 'Monthly Salary August', 52000.0),
                    (demo_id, '2026-08-03', 'Income', 'Gift', 'Birthday Gift from Family', 5000.0),
                    (demo_id, '2026-08-05', 'Expense', 'Bills', 'Electricity & Water Utilities', 1600.0),
                    (demo_id, '2026-08-07', 'Expense', 'Food', 'Weekly Groceries & Snacks', 3900.0),
                    (demo_id, '2026-08-11', 'Expense', 'Transportation', 'Petrol Refill', 2200.0),
                    (demo_id, '2026-08-15', 'Expense', 'Travel', 'Independence Day Road Trip', 4800.0),
                    (demo_id, '2026-08-20', 'Income', 'Freelance', 'Consulting & Code Review', 8000.0),
                    (demo_id, '2026-08-25', 'Expense', 'Healthcare', 'Pharmacy Medicines', 750.0),
                    (demo_id, '2026-08-28', 'Expense', 'Food', 'Cafe & Bakery Visits', 850.0),

                    # September 2026
                    (demo_id, '2026-09-01', 'Income', 'Salary', 'Monthly Salary September', 55000.0),
                    (demo_id, '2026-09-02', 'Expense', 'Bills', 'Broadband Internet Fiber', 999.0),
                    (demo_id, '2026-09-03', 'Expense', 'Food', 'Fresh Groceries', 1250.0)
                ]

                cursor.executemany('''
                    INSERT INTO transactions (user_id, date, type, category, description, amount)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', sample_transactions)
                conn.commit()

            # 4. Seed demo monthly budgets
            cursor.execute('SELECT COUNT(*) as count FROM budgets WHERE user_id = ?', (demo_id,))
            b_count = cursor.fetchone()['count']
            if b_count == 0:
                current_month = datetime.now().strftime('%Y-%m')
                prev_month = '2026-08'
                sample_budgets = [
                    (demo_id, 'Food', 5000.0, current_month),
                    (demo_id, 'Shopping', 4000.0, current_month),
                    (demo_id, 'Bills', 3000.0, current_month),
                    (demo_id, 'Transportation', 2500.0, current_month),
                    (demo_id, 'Entertainment', 2000.0, current_month),
                    (demo_id, 'Healthcare', 2000.0, current_month),
                    (demo_id, 'Food', 5000.0, prev_month),
                    (demo_id, 'Shopping', 4000.0, prev_month),
                    (demo_id, 'Bills', 3000.0, prev_month),
                    (demo_id, 'Travel', 5000.0, prev_month),
                ]
                cursor.executemany('''
                    INSERT INTO budgets (user_id, category, monthly_budget, month_year)
                    VALUES (?, ?, ?, ?)
                ''', sample_budgets)
                conn.commit()

    # ------------------- TRANSACTION METHODS (USER SCOPED) ------------------- #

    def validate_transaction(self, date_str, tx_type, category, amount):
        if not date_str:
            raise ValueError("Date is required.")
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Invalid date format. Expected YYYY-MM-DD.")

        if tx_type not in ['Income', 'Expense']:
            raise ValueError("Transaction type must be 'Income' or 'Expense'.")

        if tx_type == 'Income' and category not in Config.INCOME_CATEGORIES:
            raise ValueError(f"Invalid Income category: {category}")
        if tx_type == 'Expense' and category not in Config.EXPENSE_CATEGORIES:
            raise ValueError(f"Invalid Expense category: {category}")

        try:
            val = float(amount)
            if val <= 0:
                raise ValueError("Amount must be greater than zero.")
        except (TypeError, ValueError):
            raise ValueError("Amount must be a valid positive number.")

    def add_transaction(self, date_str, tx_type, category, description, amount, user_id=1):
        self.validate_transaction(date_str, tx_type, category, amount)
        amount = round(float(amount), 2)
        description = (description or '').strip()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transactions (user_id, date, type, category, description, amount)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, date_str, tx_type, category, description, amount))
            conn.commit()
            return cursor.lastrowid

    def get_transaction_by_id(self, tx_id, user_id=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if user_id is not None:
                cursor.execute('SELECT * FROM transactions WHERE id = ? AND user_id = ?', (tx_id, user_id))
            else:
                cursor.execute('SELECT * FROM transactions WHERE id = ?', (tx_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_transaction(self, tx_id, date_str, tx_type, category, description, amount, user_id=None):
        self.validate_transaction(date_str, tx_type, category, amount)
        amount = round(float(amount), 2)
        description = (description or '').strip()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            if user_id is not None:
                cursor.execute('''
                    UPDATE transactions
                    SET date = ?, type = ?, category = ?, description = ?, amount = ?
                    WHERE id = ? AND user_id = ?
                ''', (date_str, tx_type, category, description, amount, tx_id, user_id))
            else:
                cursor.execute('''
                    UPDATE transactions
                    SET date = ?, type = ?, category = ?, description = ?, amount = ?
                    WHERE id = ?
                ''', (date_str, tx_type, category, description, amount, tx_id))
            conn.commit()
            return cursor.rowcount > 0

    def delete_transaction(self, tx_id, user_id=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if user_id is not None:
                cursor.execute('DELETE FROM transactions WHERE id = ? AND user_id = ?', (tx_id, user_id))
            else:
                cursor.execute('DELETE FROM transactions WHERE id = ?', (tx_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_transactions(self, user_id=None, search=None, tx_type=None, category=None, start_date=None, end_date=None, sort_by='date', order='DESC', limit=None, offset=None):
        query = 'SELECT * FROM transactions'
        conditions = []
        params = []

        if user_id is not None:
            conditions.append('user_id = ?')
            params.append(user_id)

        if search:
            conditions.append('(description LIKE ? OR category LIKE ?)')
            search_param = f'%{search.strip()}%'
            params.extend([search_param, search_param])

        if tx_type and tx_type in ['Income', 'Expense']:
            conditions.append('type = ?')
            params.append(tx_type)

        if category:
            conditions.append('category = ?')
            params.append(category)

        if start_date:
            conditions.append('date >= ?')
            params.append(start_date)

        if end_date:
            conditions.append('date <= ?')
            params.append(end_date)

        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)

        allowed_sort_fields = {'date': 'date', 'amount': 'amount', 'category': 'category', 'type': 'type', 'id': 'id'}
        col = allowed_sort_fields.get(sort_by, 'date')
        direction = 'ASC' if order.upper() == 'ASC' else 'DESC'

        query += f' ORDER BY {col} {direction}, id {direction}'

        if limit is not None:
            query += ' LIMIT ?'
            params.append(int(limit))
            if offset is not None:
                query += ' OFFSET ?'
                params.append(int(offset))

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_transactions_count(self, user_id=None, search=None, tx_type=None, category=None, start_date=None, end_date=None):
        query = 'SELECT COUNT(*) as count FROM transactions'
        conditions = []
        params = []

        if user_id is not None:
            conditions.append('user_id = ?')
            params.append(user_id)

        if search:
            conditions.append('(description LIKE ? OR category LIKE ?)')
            search_param = f'%{search.strip()}%'
            params.extend([search_param, search_param])

        if tx_type and tx_type in ['Income', 'Expense']:
            conditions.append('type = ?')
            params.append(tx_type)

        if category:
            conditions.append('category = ?')
            params.append(category)

        if start_date:
            conditions.append('date >= ?')
            params.append(start_date)

        if end_date:
            conditions.append('date <= ?')
            params.append(end_date)

        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchone()['count']

    def get_all_transactions_df(self, user_id=None):
        with self.get_connection() as conn:
            if user_id is not None:
                df = pd.read_sql_query('SELECT * FROM transactions WHERE user_id = ? ORDER BY date ASC, id ASC', conn, params=(user_id,))
            else:
                df = pd.read_sql_query('SELECT * FROM transactions ORDER BY date ASC, id ASC', conn)
            if not df.empty:
                df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
                df['date'] = pd.to_datetime(df['date'])
            return df

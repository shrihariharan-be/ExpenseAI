import os
import unittest
import json
import sqlite3
import pandas as pd
import numpy as np

from config import Config
from app import app
from services.database_service import DatabaseService
from services.analytics_service import AnalyticsService
from services.export_service import ExportService

class TestExpenseTracker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure test database
        cls.test_db_path = os.path.join(Config.DATABASE_DIR, 'test_expense_tracker.db')
        if os.path.exists(cls.test_db_path):
            os.remove(cls.test_db_path)

        cls.db_service = DatabaseService(db_path=cls.test_db_path)
        cls.analytics_service = AnalyticsService(cls.db_service)
        cls.export_service = ExportService(cls.db_service)

        # Initialize and seed
        cls.db_service.init_db()

        # Set app in testing mode
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        import app as flask_module
        flask_module.db_service = cls.db_service
        flask_module.analytics_service = cls.analytics_service
        flask_module.export_service = cls.export_service
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_db_path):
            try:
                os.remove(cls.test_db_path)
            except Exception:
                pass

    def test_01_database_and_seed_data(self):
        """Verify database creation, sample data count >= 25, and idempotency."""
        self.assertTrue(os.path.exists(self.test_db_path), "Database file must exist.")

        txs = self.db_service.get_transactions()
        self.assertGreaterEqual(len(txs), 25, "At least 25 realistic sample transactions must be seeded.")

        initial_count = len(txs)
        # Attempt to seed again, should not duplicate
        self.db_service.seed_sample_data()
        count_after = len(self.db_service.get_transactions())
        self.assertEqual(initial_count, count_after, "Re-seeding must not duplicate sample transactions.")

    def test_02_crud_operations(self):
        """Test Add, Read, Update, and Delete operations."""
        # 1. Add valid transaction
        new_id = self.db_service.add_transaction(
            date_str='2026-09-03',
            tx_type='Expense',
            category='Food',
            description='Unit test lunch',
            amount=450.0
        )
        self.assertIsNotNone(new_id)

        # 2. Read
        tx = self.db_service.get_transaction_by_id(new_id)
        self.assertIsNotNone(tx)
        self.assertEqual(tx['amount'], 450.0)
        self.assertEqual(tx['category'], 'Food')
        self.assertEqual(tx['description'], 'Unit test lunch')

        # 3. Update
        updated = self.db_service.update_transaction(
            tx_id=new_id,
            date_str='2026-09-03',
            tx_type='Expense',
            category='Shopping',
            description='Updated lunch to shopping',
            amount=600.0
        )
        self.assertTrue(updated)
        tx_up = self.db_service.get_transaction_by_id(new_id)
        self.assertEqual(tx_up['category'], 'Shopping')
        self.assertEqual(tx_up['amount'], 600.0)

        # 4. Delete
        deleted = self.db_service.delete_transaction(new_id)
        self.assertTrue(deleted)
        self.assertIsNone(self.db_service.get_transaction_by_id(new_id))

    def test_03_transaction_validation(self):
        """Verify that negative amounts and invalid types/categories raise ValueError."""
        # Negative amount
        with self.assertRaises(ValueError):
            self.db_service.add_transaction('2026-09-03', 'Expense', 'Food', 'Bad amount', -100.0)

        # Zero amount
        with self.assertRaises(ValueError):
            self.db_service.add_transaction('2026-09-03', 'Expense', 'Food', 'Bad amount', 0.0)

        # Invalid Type
        with self.assertRaises(ValueError):
            self.db_service.add_transaction('2026-09-03', 'InvalidType', 'Food', 'Bad type', 100.0)

        # Invalid Category for Income
        with self.assertRaises(ValueError):
            self.db_service.add_transaction('2026-09-03', 'Income', 'Food', 'Bad category', 100.0)

        # Invalid Category for Expense
        with self.assertRaises(ValueError):
            self.db_service.add_transaction('2026-09-03', 'Expense', 'Salary', 'Bad category', 100.0)

        # Invalid Date format
        with self.assertRaises(ValueError):
            self.db_service.add_transaction('03-09-2026', 'Expense', 'Food', 'Bad date', 100.0)

    def test_04_filtering_and_search(self):
        """Verify search by keyword, type filter, category filter, and date filters."""
        # Search for 'Salary'
        salaries = self.db_service.get_transactions(search='Salary')
        self.assertTrue(len(salaries) > 0)
        for s in salaries:
            self.assertTrue('salary' in s['description'].lower() or 'salary' in s['category'].lower())

        # Type filter
        incomes = self.db_service.get_transactions(tx_type='Income')
        for inc in incomes:
            self.assertEqual(inc['type'], 'Income')

        expenses = self.db_service.get_transactions(tx_type='Expense')
        for exp in expenses:
            self.assertEqual(exp['type'], 'Expense')

        # Category filter
        food_txs = self.db_service.get_transactions(category='Food')
        for f in food_txs:
            self.assertEqual(f['category'], 'Food')

        # Date range filter
        date_txs = self.db_service.get_transactions(start_date='2026-06-01', end_date='2026-06-30')
        for d in date_txs:
            self.assertTrue('2026-06-01' <= d['date'] <= '2026-06-30')

    def test_05_pandas_and_numpy_analytics(self):
        """Test analytics calculations powered by Pandas and NumPy."""
        df = self.db_service.get_all_transactions_df()
        self.assertFalse(df.empty, "DataFrame should contain transactions.")

        # Summary metrics
        summary = self.analytics_service.get_summary_metrics(df)
        self.assertGreater(summary['total_income'], 0.0)
        self.assertGreater(summary['total_expenses'], 0.0)
        self.assertEqual(summary['current_balance'], round(summary['total_income'] - summary['total_expenses'], 2))
        self.assertNotEqual(summary['highest_expense_category'], 'None')
        self.assertGreater(summary['avg_daily_expense'], 0.0)

        # Category analysis
        cat_data = self.analytics_service.get_category_analysis(df)
        self.assertTrue(len(cat_data) > 0)
        total_pct = sum(c['percentage'] for c in cat_data)
        # Sum of rounded percentages should be close to 100%
        self.assertAlmostEqual(total_pct, 100.0, delta=1.5)

        # Monthly analysis
        monthly = self.analytics_service.get_monthly_analysis(df)
        self.assertGreaterEqual(len(monthly), 3, "Multi-month analysis should cover multiple months.")
        for m in monthly:
            self.assertEqual(m['savings'], round(m['income'] - m['expense'], 2))

        # Running balance using NumPy cumsum
        running_bal = self.analytics_service.get_running_balance(df)
        self.assertEqual(len(running_bal), len(df))
        final_running_bal = running_bal[-1]['running_balance']
        self.assertEqual(final_running_bal, summary['current_balance'])

        # Spending trend
        trend = self.analytics_service.get_spending_trend(df)
        self.assertEqual(len(trend['dates']), len(trend['daily_expenses']))
        self.assertEqual(len(trend['dates']), len(trend['cumulative_expenses']))

    def test_06_flask_web_routes(self):
        """Test all Flask web routes and HTTP responses."""
        # 1. Index redirect
        res = self.client.get('/')
        self.assertEqual(res.status_code, 302)

        # 2. Dashboard
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Financial Overview', res.data)
        self.assertIn(b'Current Balance', res.data)

        # 3. Add Transaction page GET
        res = self.client.get('/add')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Add New Transaction', res.data)

        # 4. Add Transaction POST (Valid)
        res = self.client.post('/add', data={
            'type': 'Expense',
            'date': '2026-09-03',
            'category': 'Food',
            'description': 'Automated Test Meal',
            'amount': '320.50'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Automated Test Meal', res.data)

        # 5. Add Transaction POST (Invalid Amount)
        res = self.client.post('/add', data={
            'type': 'Expense',
            'date': '2026-09-03',
            'category': 'Food',
            'description': 'Negative Meal',
            'amount': '-50'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Amount must be greater than zero', res.data)

        # 6. Transactions page with filter
        res = self.client.get('/transactions?search=Automated+Test+Meal')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Automated Test Meal', res.data)

        # 7. Analytics page
        res = self.client.get('/analytics')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Financial Analytics', res.data)
        self.assertIn(b'Category Analysis', res.data)

        # 8. Reports page
        for p in ['daily', 'weekly', 'monthly', 'all']:
            res = self.client.get(f'/reports?period={p}')
            self.assertEqual(res.status_code, 200)
            self.assertIn(b'Generate Financial Report', res.data)

        # 9. Export CSV
        res = self.client.get('/export')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, 'text/csv; charset=utf-8')
        self.assertIn(b'Amount (INR)', res.data)
        self.assertIn(b'Salary', res.data)

    def test_07_api_json_endpoints(self):
        """Test all REST API routes and JSON response structures."""
        # 1. /api/dashboard-data
        res = self.client.get('/api/dashboard-data')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertIn('summary', data['data'])
        self.assertIn('category_chart', data['data'])
        self.assertIn('monthly_chart', data['data'])

        # 2. /api/category-data
        res = self.client.get('/api/category-data')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertIn('categories', data)
        self.assertIn('labels', data)
        self.assertIn('amounts', data)

        # 3. /api/monthly-data
        res = self.client.get('/api/monthly-data')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertIn('months', data)
        self.assertIn('income', data)
        self.assertIn('expense', data)
        self.assertIn('savings', data)

        # 4. /api/spending-trend
        res = self.client.get('/api/spending-trend')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertIn('dates', data)
        self.assertIn('daily_expenses', data)
        self.assertIn('cumulative_expenses', data)

    def test_08_empty_database_handling(self):
        """Ensure analytics and routes never crash with an empty database."""
        empty_db_path = os.path.join(Config.DATABASE_DIR, 'empty_test.db')
        if os.path.exists(empty_db_path):
            os.remove(empty_db_path)

        empty_db = DatabaseService(db_path=empty_db_path)
        with empty_db.get_connection() as conn:
            conn.execute('''
                CREATE TABLE transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    type TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT,
                    amount REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        empty_analytics = AnalyticsService(empty_db)

        # Summary on empty
        summary = empty_analytics.get_summary_metrics()
        self.assertEqual(summary['total_income'], 0.0)
        self.assertEqual(summary['total_expenses'], 0.0)
        self.assertEqual(summary['current_balance'], 0.0)
        self.assertEqual(summary['total_transactions'], 0)

        # Category on empty
        cats = empty_analytics.get_category_analysis()
        self.assertEqual(cats, [])

        # Monthly on empty
        monthly = empty_analytics.get_monthly_analysis()
        self.assertEqual(monthly, [])

        # Clean up
        if os.path.exists(empty_db_path):
            os.remove(empty_db_path)

if __name__ == '__main__':
    unittest.main()

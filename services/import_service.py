import csv
import io
from datetime import datetime
from config import Config

class ImportService:
    def __init__(self, db_service):
        self.db_service = db_service

    def get_template_csv(self):
        """Returns a sample CSV string for users to download and fill."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Date', 'Type', 'Category', 'Description', 'Amount'])
        writer.writerow(['2026-09-01', 'Income', 'Salary', 'Monthly Salary', '50000'])
        writer.writerow(['2026-09-02', 'Expense', 'Food', 'Grocery Shopping', '2500'])
        writer.writerow(['2026-09-03', 'Expense', 'Transportation', 'Petrol Refill', '1500'])
        writer.writerow(['2026-09-04', 'Expense', 'Bills', 'Electricity Bill', '1200'])
        return output.getvalue()

    def import_transactions_from_csv(self, file_storage, user_id):
        """
        Parses an uploaded CSV file, validates rows, and bulk inserts valid transactions.
        """
        if not file_storage or not file_storage.filename:
            return {'success': False, 'error': 'No file was uploaded.'}

        if not file_storage.filename.lower().endswith('.csv'):
            return {'success': False, 'error': 'Only .csv files are supported.'}

        content = file_storage.read().decode('utf-8', errors='ignore')
        reader = csv.reader(io.StringIO(content))

        rows = list(reader)
        if not rows:
            return {'success': False, 'error': 'The uploaded CSV file is empty.'}

        # Validate headers
        header = [col.strip().lower() for col in rows[0]]
        required_cols = ['date', 'type', 'category', 'amount']
        for col in required_cols:
            if col not in header:
                return {
                    'success': False,
                    'error': f"Missing required column header '{col}'. Header must contain: Date, Type, Category, Description, Amount."
                }

        date_idx = header.index('date')
        type_idx = header.index('type')
        cat_idx = header.index('category')
        amt_idx = header.index('amount')
        desc_idx = header.index('description') if 'description' in header else -1

        valid_transactions = []
        errors = []
        total_data_rows = len(rows) - 1

        for idx, row in enumerate(rows[1:], start=2):
            if not row or all(not cell.strip() for cell in row):
                continue  # skip empty lines

            try:
                date_val = row[date_idx].strip()
                type_val = row[type_idx].strip().capitalize()
                cat_val = row[cat_idx].strip()
                desc_val = row[desc_idx].strip() if desc_idx != -1 and desc_idx < len(row) else ''
                amt_str = row[amt_idx].strip().replace('₹', '').replace(',', '')

                # Validations
                datetime.strptime(date_val, '%Y-%m-%d')

                if type_val not in ['Income', 'Expense']:
                    raise ValueError(f"Type must be 'Income' or 'Expense', got '{type_val}'")

                if type_val == 'Income' and cat_val not in Config.INCOME_CATEGORIES:
                    raise ValueError(f"Invalid Income category '{cat_val}'")
                if type_val == 'Expense' and cat_val not in Config.EXPENSE_CATEGORIES:
                    raise ValueError(f"Invalid Expense category '{cat_val}'")

                amount = float(amt_str)
                if amount <= 0:
                    raise ValueError(f"Amount must be greater than zero, got '{amount}'")

                valid_transactions.append((
                    date_val, type_val, cat_val, desc_val, round(amount, 2)
                ))
            except Exception as e:
                errors.append({'row': idx, 'error': str(e), 'data': ', '.join(row)})

        # Insert valid rows with duplicate avoidance
        imported_count = 0
        duplicates_skipped = 0
        if valid_transactions:
            with self.db_service.get_connection() as conn:
                cursor = conn.cursor()
                for t in valid_transactions:
                    # Check for exact duplicate
                    cursor.execute('''
                        SELECT id FROM transactions 
                        WHERE user_id = ? AND date = ? AND type = ? AND category = ? AND description = ? AND amount = ?
                        LIMIT 1
                    ''', (user_id, t[0], t[1], t[2], t[3], t[4]))
                    existing = cursor.fetchone()
                    if existing:
                        duplicates_skipped += 1
                        continue

                    cursor.execute('''
                        INSERT INTO transactions (user_id, date, type, category, description, amount)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (user_id, t[0], t[1], t[2], t[3], t[4]))
                    imported_count += 1
                conn.commit()

        return {
            'success': True,
            'total_rows': total_data_rows,
            'imported_count': imported_count,
            'duplicates_skipped': duplicates_skipped,
            'failed_count': len(errors),
            'errors': errors
        }

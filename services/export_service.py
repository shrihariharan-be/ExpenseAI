import os
import csv
import io
from config import Config

class ExportService:
    def __init__(self, db_service):
        self.db_service = db_service
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        data_dir = Config.DATA_DIR
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)

    def export_transactions_to_csv_file(self, transactions=None, file_path=None, user_id=None):
        self._ensure_data_dir()
        target_path = file_path or Config.EXPORT_CSV_PATH

        if transactions is None:
            transactions = self.db_service.get_transactions(user_id=user_id, limit=100000)

        with open(target_path, mode='w', newline='', encoding='utf-8') as csv_file:
            fieldnames = ['ID', 'Date', 'Type', 'Category', 'Description', 'Amount', 'Created At']
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()

            for tx in transactions:
                writer.writerow({
                    'ID': tx.get('id', ''),
                    'Date': tx.get('date', ''),
                    'Type': tx.get('type', ''),
                    'Category': tx.get('category', ''),
                    'Description': tx.get('description', ''),
                    'Amount': tx.get('amount', 0.0),
                    'Created At': tx.get('created_at', '')
                })

        return target_path

    def export_transactions_to_csv_string(self, transactions=None, user_id=None):
        if transactions is None:
            transactions = self.db_service.get_transactions(user_id=user_id, limit=100000)

        output = io.StringIO()
        fieldnames = ['ID', 'Date', 'Type', 'Category', 'Description', 'Amount (INR)', 'Created At']
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for tx in transactions:
            writer.writerow({
                'ID': tx.get('id', ''),
                'Date': tx.get('date', ''),
                'Type': tx.get('type', ''),
                'Category': tx.get('category', ''),
                'Description': tx.get('description', ''),
                'Amount (INR)': f"{float(tx.get('amount', 0.0)):.2f}",
                'Created At': tx.get('created_at', '')
            })

        return output.getvalue()

import io
import json
import os
import pytest
from PIL import Image
from config import Config

def test_pwa_manifest_and_icons(client):
    # 1. Manifest endpoint
    res = client.get('/static/manifest.json')
    assert res.status_code == 200
    manifest = json.loads(res.data)
    assert "ExpenseAI" in manifest['name']
    assert manifest['short_name'] == "ExpenseAI"
    assert manifest['display'] == "standalone"
    assert manifest['start_url'] == "/dashboard"
    assert manifest['theme_color'] == "#2563eb"
    assert len(manifest['icons']) >= 2

    # 2. Verify icon files exist and are valid PNG images
    icon_192_path = os.path.join(Config.BASE_DIR, 'static', 'images', 'icon-192.png')
    icon_512_path = os.path.join(Config.BASE_DIR, 'static', 'images', 'icon-512.png')
    assert os.path.exists(icon_192_path)
    assert os.path.exists(icon_512_path)

    with Image.open(icon_192_path) as img192:
        assert img192.size == (192, 192)
        assert img192.format == 'PNG'

    with Image.open(icon_512_path) as img512:
        assert img512.size == (512, 512)
        assert img512.format == 'PNG'

def test_pwa_service_worker_and_offline(client):
    # 1. Service worker endpoint
    sw_res = client.get('/sw.js')
    assert sw_res.status_code == 200
    assert 'javascript' in sw_res.content_type
    assert sw_res.headers.get('Service-Worker-Allowed') == '/'
    assert b'expenseai-shell-v1' in sw_res.data

    # 2. Offline fallback page
    off_res = client.get('/offline')
    assert off_res.status_code == 200
    assert b'You Are Currently Offline' in off_res.data
    assert b'Data Protection Guard' in off_res.data

def test_production_error_handlers(client):
    # 1. 404 for standard web navigation -> returns branded HTML error template
    res_html = client.get('/this-route-does-not-exist-at-all')
    assert res_html.status_code == 404
    assert b'404' in res_html.data
    assert b'Page Not Found' in res_html.data

    # 2. 404 for API request -> returns structured JSON error response
    res_api = client.get('/api/invalid-resource')
    assert res_api.status_code == 404
    api_data = json.loads(res_api.data)
    assert api_data['success'] is False
    assert '404' in api_data['error']

def test_sqlite_indexing_and_wal(db_service):
    # Verify indexes exist
    with db_service.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row['name'] for row in cursor.fetchall()]
        assert 'idx_tx_user_date' in indexes
        assert 'idx_tx_user_type_cat' in indexes
        assert 'idx_budgets_user_month' in indexes
        assert 'idx_users_email' in indexes

        # Verify WAL mode
        cursor.execute("PRAGMA journal_mode")
        journal_mode = cursor.fetchone()[0]
        assert journal_mode.lower() in ('wal', 'memory')

def test_ai_insufficient_data_handling(db_service):
    from services.ai_service import AIService
    from services.budget_service import BudgetService

    # Create empty user
    uid = db_service.create_user('Empty AI User', 'empty_ai@example.com', 'EmptyPass@123', role='user')
    ai_svc = AIService(db_service, budget_service=BudgetService(db_service))

    # 1. Zero transactions
    pred_zero = ai_svc.predict_next_month_expenses(user_id=uid)
    assert pred_zero['has_sufficient_data'] is False
    assert pred_zero['predicted_total'] == 0.0

    # 2. Single transaction
    db_service.add_transaction('2026-09-01', 'Expense', 'Food', 'Single Meal', 500.0, user_id=uid)
    pred_one = ai_svc.predict_next_month_expenses(user_id=uid)
    assert pred_one['has_sufficient_data'] is False

def test_csv_duplicate_prevention(client, db_service):
    uid = db_service.create_user('CSV User', 'csv_dedup@example.com', 'CsvPass@123', role='user')
    from services.import_service import ImportService
    import_svc = ImportService(db_service)

    csv_content = (
        "Date,Type,Category,Description,Amount\n"
        "2026-09-01,Expense,Food,Grocery Dedup Test,1200.00\n"
        "2026-09-02,Expense,Bills,Power Bill Dedup,1800.00\n"
    )

    class DummyFile:
        def __init__(self, content):
            self.content = content.encode('utf-8')
            self.filename = 'dedup.csv'
        def read(self):
            return self.content

    # First import: should insert 2
    res1 = import_svc.import_transactions_from_csv(DummyFile(csv_content), user_id=uid)
    assert res1['success'] is True
    assert res1['imported_count'] == 2
    assert res1['duplicates_skipped'] == 0

    # Second import with identical content: should detect 2 duplicates and insert 0
    res2 = import_svc.import_transactions_from_csv(DummyFile(csv_content), user_id=uid)
    assert res2['success'] is True
    assert res2['imported_count'] == 0
    assert res2['duplicates_skipped'] == 2

def test_apk_download_endpoint(client):
    res = client.get('/download/apk')
    assert res.status_code == 200
    assert 'android.package-archive' in res.content_type
    assert 'ExpenseAI.apk' in res.headers.get('Content-Disposition', '')
    assert len(res.data) > 1000000  # > 1MB real APK binary

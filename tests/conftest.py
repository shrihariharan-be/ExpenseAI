import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import pytest
from config import Config
from app import app as flask_app
from services.database_service import DatabaseService
from services.analytics_service import AnalyticsService
from services.export_service import ExportService
from services.budget_service import BudgetService
from services.ai_service import AIService
from services.import_service import ImportService
from services.pdf_service import PDFReportService

@pytest.fixture(scope='session')
def test_db_path(tmp_path_factory):
    fn = tmp_path_factory.mktemp("data") / "test_expense_tracker.db"
    return str(fn)

@pytest.fixture(scope='session')
def db_service(test_db_path):
    svc = DatabaseService(db_path=test_db_path)
    svc.init_db()
    return svc

@pytest.fixture(scope='session')
def app_instance(db_service):
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    
    # Inject test database service across modules
    import app as app_module
    app_module.db_service = db_service
    app_module.analytics_service = AnalyticsService(db_service)
    app_module.export_service = ExportService(db_service)
    app_module.budget_service = BudgetService(db_service)
    app_module.ai_service = AIService(db_service)
    app_module.import_service = ImportService(db_service)
    app_module.pdf_service = PDFReportService(app_module.analytics_service, db_service)

    return flask_app

@pytest.fixture
def client(app_instance):
    return app_instance.test_client()

@pytest.fixture
def auth_client(app_instance, db_service):
    c = app_instance.test_client()
    demo = db_service.get_user_by_email('demo@example.com')
    demo_id = demo['id'] if demo else 1
    with c.session_transaction() as sess:
        sess['user_id'] = demo_id
        sess['user_email'] = 'demo@example.com'
        sess['user_name'] = 'Demo User'
        sess['user_role'] = 'user'
    return c

@pytest.fixture
def admin_client(app_instance, db_service):
    c = app_instance.test_client()
    admin = db_service.get_user_by_email(Config.ADMIN_EMAIL)
    admin_id = admin['id'] if admin else 2
    with c.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['user_email'] = Config.ADMIN_EMAIL
        sess['user_name'] = 'System Administrator'
        sess['user_role'] = 'admin'
    return c

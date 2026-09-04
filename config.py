import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    BASE_DIR = BASE_DIR
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development').lower()

    # Secret Key: Enforce environment variable in production
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        if FLASK_ENV == 'production':
            raise RuntimeError("CRITICAL: SECRET_KEY environment variable must be set in production mode.")
        SECRET_KEY = 'dev-secret-key-change-in-production'

    DATABASE_URL = os.environ.get('DATABASE_URL')
    DATABASE_DIR = os.path.join(BASE_DIR, 'database')
    DATABASE_PATH = os.environ.get('SQLITE_PATH') or os.path.join(DATABASE_DIR, 'expense_tracker.db')
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    EXPORT_CSV_PATH = os.path.join(DATA_DIR, 'transactions.csv')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    CURRENCY_SYMBOL = '₹'
    
    # Administrator Configuration: Enforce environment variables in production
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
    ADMIN_NAME = os.environ.get('ADMIN_NAME', 'System Administrator')

    if not ADMIN_EMAIL:
        if FLASK_ENV == 'production':
            raise RuntimeError("CRITICAL: ADMIN_EMAIL environment variable must be set in production mode.")
        ADMIN_EMAIL = 'admin@example.com'

    if not ADMIN_PASSWORD:
        if FLASK_ENV == 'production':
            raise RuntimeError("CRITICAL: ADMIN_PASSWORD environment variable must be set in production mode.")
        ADMIN_PASSWORD = 'DevAdminPassword123!'

    ADMIN_EMAIL = ADMIN_EMAIL.strip().lower()

    # Session & Cookie Security
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() in ('true', '1')
    
    INCOME_CATEGORIES = [
        'Salary',
        'Freelance',
        'Business',
        'Investment',
        'Gift',
        'Other'
    ]
    
    EXPENSE_CATEGORIES = [
        'Food',
        'Transportation',
        'Shopping',
        'Entertainment',
        'Bills',
        'Healthcare',
        'Education',
        'Travel',
        'Other'
    ]

    CATEGORY_COLORS = {
        'Food': '#F97316',          # Orange
        'Transportation': '#06B6D4',  # Cyan
        'Shopping': '#EC4899',        # Pink
        'Entertainment': '#8B5CF6',   # Purple
        'Bills': '#EF4444',           # Red
        'Healthcare': '#10B981',      # Emerald
        'Education': '#3B82F6',       # Blue
        'Travel': '#F59E0B',          # Amber
        'Salary': '#16A34A',          # Green
        'Freelance': '#14B8A6',       # Teal
        'Business': '#6366F1',        # Indigo
        'Investment': '#84CC16',      # Lime
        'Gift': '#D946EF',            # Fuchsia
        'Other': '#64748B'            # Slate
    }

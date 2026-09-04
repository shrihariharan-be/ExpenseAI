import io
import json
import pytest

def test_web_routes(auth_client):
    # Dashboard
    res = auth_client.get('/dashboard')
    assert res.status_code == 200
    assert b'Financial Overview' in res.data

    # Transactions
    res = auth_client.get('/transactions')
    assert res.status_code == 200

    # Expenses alias route
    res = auth_client.get('/expenses')
    assert res.status_code == 200
    assert b'Transactions Management' in res.data

    # Budgets
    res = auth_client.get('/budgets')
    assert res.status_code == 200
    assert b'Monthly Budget Planner' in res.data

    # AI Insights
    res = auth_client.get('/insights')
    assert res.status_code == 200
    assert b'Machine Learning Expense Forecast' in res.data

    # Analytics & Reports
    assert auth_client.get('/analytics').status_code == 200
    assert auth_client.get('/reports').status_code == 200

def test_csv_import_route(auth_client):
    csv_data = (
        "Date,Type,Category,Description,Amount\n"
        "2026-09-02,Expense,Food,Imported Lunch,420.00\n"
        "2026-09-02,Income,Freelance,Design gig,5000.00\n"
        "invalid-date,Expense,Food,Bad row,100.00\n"
    )
    data = {
        'file': (io.BytesIO(csv_data.encode('utf-8')), 'test_import.csv')
    }
    res = auth_client.post('/import', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert res.status_code == 200
    assert b'Import Complete' in res.data
    assert b'Imported Lunch' in res.data or b'Import Execution Summary' in res.data

def test_pdf_export_route(auth_client):
    res = auth_client.get('/export/pdf')
    assert res.status_code == 200
    assert res.content_type == 'application/pdf'
    assert len(res.data) > 1000

def test_rest_apis(auth_client):
    # 1. GET /api/transactions
    res = auth_client.get('/api/transactions')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['success'] is True
    assert 'transactions' in data

    # 2. POST /api/transactions
    new_tx = {
        'date': '2026-09-03',
        'type': 'Expense',
        'category': 'Food',
        'description': 'REST API Food',
        'amount': 250.0
    }
    res = auth_client.post('/api/transactions', json=new_tx)
    assert res.status_code == 201
    post_res = json.loads(res.data)
    assert post_res['success'] is True
    created_id = post_res['id']

    # 3. GET /api/transactions/<id>
    res = auth_client.get(f'/api/transactions/{created_id}')
    assert res.status_code == 200

    # 4. PUT /api/transactions/<id>
    res = auth_client.put(f'/api/transactions/{created_id}', json={'amount': 300.0})
    assert res.status_code == 200

    # 5. DELETE /api/transactions/<id>
    res = auth_client.delete(f'/api/transactions/{created_id}')
    assert res.status_code == 200

    # 6. GET /api/budgets
    res = auth_client.get('/api/budgets')
    assert res.status_code == 200
    assert json.loads(res.data)['success'] is True

    # 7. GET /api/ai-insights
    res = auth_client.get('/api/ai-insights')
    assert res.status_code == 200
    ai_json = json.loads(res.data)
    assert ai_json['success'] is True
    assert 'prediction' in ai_json

def test_help_profile_and_onboarding(auth_client):
    # Help Guide
    help_res = auth_client.get('/help')
    assert help_res.status_code == 200
    assert b'How to Use ExpenseAI' in help_res.data
    assert b'Add Transactions' in help_res.data

    # User Profile
    prof_res = auth_client.get('/profile')
    assert prof_res.status_code == 200
    assert b'User Profile & Account Settings' in prof_res.data

    # Onboarding Completion API
    onb_res = auth_client.post('/api/onboarding/complete')
    assert onb_res.status_code == 200
    assert json.loads(onb_res.data)['success'] is True

def test_transaction_ownership_authorization(client, db_service):
    # Create two isolated users
    u1_id = db_service.create_user('User One', 'u1@example.com', 'PassOne@123', role='user')
    u2_id = db_service.create_user('User Two', 'u2@example.com', 'PassTwo@123', role='user')

    # U1 creates a transaction
    tx_id = db_service.add_transaction('2026-09-01', 'Expense', 'Food', 'U1 Private Dinner', 150.0, user_id=u1_id)

    # U2 logs in
    with client.session_transaction() as sess:
        sess['user_id'] = u2_id
        sess['user_email'] = 'u2@example.com'
        sess['user_role'] = 'user'

    # U2 attempts to edit U1's transaction -> Forbidden / Access denied
    edit_res = client.get(f'/edit/{tx_id}', follow_redirects=True)
    assert b'Unauthorized' in edit_res.data

    # U2 attempts to delete U1's transaction -> Forbidden / Access denied
    del_res = client.post(f'/delete/{tx_id}', follow_redirects=True)
    assert b'Unauthorized' in del_res.data

    # Verify transaction still exists untouched
    tx = db_service.get_transaction_by_id(tx_id)
    assert tx is not None
    assert tx['amount'] == 150.0

def test_api_authentication_and_financial_data_isolation(client, db_service):
    # 1. Verify unauthenticated access to financial records returns 401
    anon_headers = {'X-Anonymous': '1'}
    for endpoint in ['/api/transactions', '/api/expenses', '/api/income', '/api/budgets']:
        res = client.get(endpoint, headers=anon_headers)
        assert res.status_code == 401
        data = json.loads(res.data)
        assert data['success'] is False
        assert 'Authentication required' in data['error']

    # 2. Test API login and logout
    login_res = client.post('/api/login', json={'email': 'demo@example.com', 'password': 'Demo@123'})
    assert login_res.status_code == 200
    assert json.loads(login_res.data)['success'] is True

    # Bad credentials
    bad_res = client.post('/api/login', json={'email': 'demo@example.com', 'password': 'WrongPassword'})
    assert bad_res.status_code == 401

    # 3. Create isolated user accounts for data isolation and ID manipulation test
    u1_id = db_service.create_user('Data Owner', 'owner@example.com', 'PassOwner@123')
    u2_id = db_service.create_user('Data Attacker', 'attacker@example.com', 'PassAttacker@123')

    # U1 creates private transaction
    u1_tx_id = db_service.add_transaction('2026-09-02', 'Expense', 'Food', 'Private Lunch', 350.0, user_id=u1_id)

    # U2 logs in via session
    with client.session_transaction() as sess:
        sess['user_id'] = u2_id
        sess['user_email'] = 'attacker@example.com'
        sess['user_role'] = 'user'

    # ID manipulation: U2 attempts GET, PUT, DELETE on U1's transaction
    res_get = client.get(f'/api/transactions/{u1_tx_id}')
    assert res_get.status_code == 403
    assert 'Forbidden' in json.loads(res_get.data)['error']

    res_put = client.put(f'/api/transactions/{u1_tx_id}', json={'amount': 9999.0})
    assert res_put.status_code == 403

    res_del = client.delete(f'/api/transactions/{u1_tx_id}')
    assert res_del.status_code == 403

    # Verify U1's transaction was never tampered with
    tx = db_service.get_transaction_by_id(u1_tx_id)
    assert tx['amount'] == 350.0

    # 4. Test API logout
    logout_res = client.get('/api/logout')
    assert logout_res.status_code == 200
    assert json.loads(logout_res.data)['success'] is True


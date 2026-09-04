import pytest
from config import Config

def test_registration_and_login(client, db_service):
    # 1. Reject weak password
    weak_res = client.post('/register', data={
        'full_name': 'Test Weak',
        'email': 'weak@example.com',
        'password': 'short',
        'confirm_password': 'short'
    }, follow_redirects=True)
    assert b'Password must be at least 8 characters long' in weak_res.data

    # 2. Reject password missing number
    no_num_res = client.post('/register', data={
        'full_name': 'Test NoNum',
        'email': 'nonum@example.com',
        'password': 'PasswordOnly',
        'confirm_password': 'PasswordOnly'
    }, follow_redirects=True)
    assert b'Password must contain at least one number' in no_num_res.data

    # 3. Successful registration with strong password
    reg_res = client.post('/register', data={
        'full_name': 'Alice Developer',
        'email': 'alice@example.com',
        'password': 'SecurePassword@123',
        'confirm_password': 'SecurePassword@123'
    }, follow_redirects=True)
    assert b'Account created successfully' in reg_res.data

    # 4. Verify user exists in database
    user = db_service.get_user_by_email('alice@example.com')
    assert user is not None
    assert user['full_name'] == 'Alice Developer'
    assert user['role'] == 'user'

    # 5. Successful Login via email
    login_res = client.post('/login', data={
        'email': 'alice@example.com',
        'password': 'SecurePassword@123'
    }, follow_redirects=True)
    assert login_res.status_code == 200
    assert b'Welcome back, Alice Developer' in login_res.data

    # 6. Logout
    logout_res = client.get('/logout', follow_redirects=True)
    assert b'You have been signed out' in logout_res.data

def test_duplicate_user_validation(client):
    # Attempting to register with existing email
    res = client.post('/register', data={
        'full_name': 'Duplicate User',
        'email': 'alice@example.com',
        'password': 'Password@123',
        'confirm_password': 'Password@123'
    }, follow_redirects=True)
    assert b'already exists' in res.data

def test_forgot_password_flow(client):
    res = client.post('/forgot-password', data={
        'email': 'alice@example.com'
    })
    assert res.status_code == 200
    assert b'Recovery Simulated for:' in res.data

def test_auth_status_and_root_navigation(client):
    # 1. Logged out state
    res = client.get('/api/auth/status')
    assert res.status_code == 200
    data = res.get_json()
    assert data['authenticated'] is False
    assert data['user'] is None

    # 2. Root / while logged out redirects to /login
    root_res = client.get('/', follow_redirects=False)
    assert root_res.status_code == 302
    assert '/login' in root_res.headers['Location']

    # 3. Login
    login_res = client.post('/login', data={
        'email': 'demo@example.com',
        'password': 'Demo@123'
    }, follow_redirects=True)
    assert login_res.status_code == 200

    # 4. Auth status while logged in
    auth_status = client.get('/api/auth/status')
    assert auth_status.status_code == 200
    auth_data = auth_status.get_json()
    assert auth_data['authenticated'] is True
    assert auth_data['user']['email'] == 'demo@example.com'

    # 5. Root / while logged in redirects to /dashboard
    auth_root = client.get('/', follow_redirects=False)
    assert auth_root.status_code == 302
    assert '/dashboard' in auth_root.headers['Location']

def test_direct_protected_url_access_denied_when_logged_out(client):
    protected_urls = [
        '/dashboard',
        '/expenses',
        '/transactions',
        '/income',
        '/ai',
        '/budgets',
        '/analytics',
        '/reports',
        '/profile',
        '/admin'
    ]

    for url in protected_urls:
        res = client.get(url, headers={'X-Anonymous': '1'}, follow_redirects=False)
        assert res.status_code == 302, f"Expected 302 redirect for {url}, got {res.status_code}"
        assert '/login' in res.headers['Location'], f"Expected redirect to /login for {url}, got {res.headers['Location']}"

def test_admin_route_access_restriction(client, db_service):
    # 1. Normal user cannot access /admin
    client.post('/login', data={
        'email': 'demo@example.com',
        'password': 'Demo@123'
    }, follow_redirects=True)

    admin_attempt = client.get('/admin', follow_redirects=False)
    assert admin_attempt.status_code == 302
    assert '/dashboard' in admin_attempt.headers['Location']

    admin_attempt_followed = client.get('/admin', follow_redirects=True)
    assert b'Access denied: Administrator privileges required' in admin_attempt_followed.data

    # 2. Administrator CAN access /admin
    client.get('/logout')
    admin_login = client.post('/login', data={
        'email': Config.ADMIN_EMAIL,
        'password': Config.ADMIN_PASSWORD
    }, follow_redirects=True)
    assert admin_login.status_code == 200

    admin_ok = client.get('/admin')
    assert admin_ok.status_code == 200
    assert b'Admin Panel' in admin_ok.data

def test_logout_invalidates_session_and_sets_cache_headers(client):
    # Log in first
    client.post('/login', data={
        'email': 'demo@example.com',
        'password': 'Demo@123'
    }, follow_redirects=True)

    # Logout
    logout_res = client.get('/logout', follow_redirects=False)
    assert logout_res.status_code == 302
    assert '/login' in logout_res.headers['Location']
    assert 'no-store' in logout_res.headers.get('Cache-Control', '')

    # Session is cleared
    with client.session_transaction() as sess:
        assert 'user_id' not in sess

    # Subsequent access to protected page must redirect to login
    subseq = client.get('/dashboard', headers={'X-Anonymous': '1'}, follow_redirects=False)
    assert subseq.status_code == 302
    assert '/login' in subseq.headers['Location']

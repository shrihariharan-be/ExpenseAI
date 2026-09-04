import pytest
from config import Config

def test_admin_role_access(auth_client, admin_client):
    # 1. Regular user trying to access /admin -> Access Denied
    res = auth_client.get('/admin', follow_redirects=True)
    assert b'Administrator privileges required' in res.data or res.status_code == 403

    # 2. Administrator accessing /admin -> Success
    res_admin = admin_client.get('/admin')
    assert res_admin.status_code == 200
    assert b'Administrator Control Panel' in res_admin.data
    assert b'User Management' in res_admin.data

def test_admin_system_stats_and_user_management(admin_client, db_service):
    # 1. Test system stats
    stats = db_service.get_system_overview_stats()
    assert stats['total_users'] >= 2
    assert stats['total_transactions'] > 0
    assert stats['total_income'] > 0

    # 2. Create a disposable user for deletion test
    test_uid = db_service.create_user(
        full_name='Delete Candidate',
        email='to_delete@example.com',
        password='TempPassword@123',
        role='user'
    )
    assert test_uid is not None

    # 3. Admin deletes the user
    del_res = admin_client.post(f'/admin/delete-user/{test_uid}', follow_redirects=True)
    assert b'deleted successfully' in del_res.data
    assert db_service.get_user_by_id(test_uid) is None

    # 4. Self-deletion protection
    admin = db_service.get_user_by_email(Config.ADMIN_EMAIL)
    with pytest.raises(ValueError, match="cannot delete your own"):
        db_service.delete_user_by_admin(admin['id'], admin_user_id=admin['id'])

    # 5. Primary admin account deletion protection
    with pytest.raises(ValueError, match="primary system administrator"):
        db_service.delete_user_by_admin(admin['id'], admin_user_id=999)

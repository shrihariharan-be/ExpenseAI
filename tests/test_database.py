import pytest

def test_database_seeding_and_crud(db_service):
    # Demo transactions seeded
    txs = db_service.get_transactions(user_id=1)
    assert len(txs) >= 25

    # Add transaction
    new_id = db_service.add_transaction(
        date_str='2026-09-03',
        tx_type='Income',
        category='Salary',
        description='Bonus Salary',
        amount=15000.0,
        user_id=1
    )
    assert new_id is not None

    # Read transaction
    tx = db_service.get_transaction_by_id(new_id, user_id=1)
    assert tx is not None
    assert tx['amount'] == 15000.0

    # Update transaction
    updated = db_service.update_transaction(
        tx_id=new_id,
        date_str='2026-09-03',
        tx_type='Income',
        category='Freelance',
        description='Updated Bonus',
        amount=18000.0,
        user_id=1
    )
    assert updated is True
    tx_up = db_service.get_transaction_by_id(new_id, user_id=1)
    assert tx_up['category'] == 'Freelance'
    assert tx_up['amount'] == 18000.0

    # Delete transaction
    deleted = db_service.delete_transaction(new_id, user_id=1)
    assert deleted is True
    assert db_service.get_transaction_by_id(new_id, user_id=1) is None

def test_user_data_isolation(db_service):
    # Create User 2
    u2_id = db_service.create_user('isolation_user', 'iso@test.com', 'IsoPassword@123')

    # Add transaction for User 2
    tx2_id = db_service.add_transaction(
        date_str='2026-09-03',
        tx_type='Expense',
        category='Food',
        description='User 2 Lunch',
        amount=400.0,
        user_id=u2_id
    )

    # User 1 should NOT see User 2's transaction
    u1_txs = db_service.get_transactions(user_id=1)
    u1_ids = [t['id'] for t in u1_txs]
    assert tx2_id not in u1_ids

    # User 1 cannot delete User 2's transaction
    deleted_by_other = db_service.delete_transaction(tx2_id, user_id=1)
    assert deleted_by_other is False
    assert db_service.get_transaction_by_id(tx2_id, user_id=u2_id) is not None

def test_input_validation(db_service):
    with pytest.raises(ValueError):
        db_service.add_transaction('2026-09-03', 'Expense', 'Food', 'Negative', -50.0, user_id=1)

    with pytest.raises(ValueError):
        db_service.add_transaction('2026-09-03', 'InvalidType', 'Food', 'Bad Type', 50.0, user_id=1)

import pytest
from services.budget_service import BudgetService

def test_budget_management(db_service):
    budget_service = BudgetService(db_service)
    user_id = 1
    month = '2026-09'

    # 1. Set budget
    bid = budget_service.set_budget(user_id, 'Food', 6000.0, month)
    assert bid is not None

    # 2. Fetch budget status
    status = budget_service.get_budget_status(user_id, month)
    assert status['month_year'] == month
    assert status['total_budget'] > 0

    food_budget = next((c for c in status['categories'] if c['category'] == 'Food'), None)
    assert food_budget is not None
    assert food_budget['budget'] == 6000.0
    assert food_budget['spent'] > 0
    assert food_budget['status'] in ['safe', 'warning', 'exceeded']

    # 3. Test Overspending alert
    # Set a tiny budget for Shopping to trigger alert
    budget_service.set_budget(user_id, 'Bills', 500.0, month)
    status2 = budget_service.get_budget_status(user_id, month)
    bills_cat = next((c for c in status2['categories'] if c['category'] == 'Bills'), None)
    assert bills_cat['status'] == 'exceeded'
    assert len(status2['alerts']) > 0

    # 4. Delete budget
    deleted = budget_service.delete_budget(food_budget['id'], user_id)
    assert deleted is True

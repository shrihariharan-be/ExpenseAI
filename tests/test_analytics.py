import pytest
from services.analytics_service import AnalyticsService

def test_analytics_calculations(db_service):
    analytics = AnalyticsService(db_service)
    user_id = 1

    # 1. Summary Metrics
    summary = analytics.get_summary_metrics(user_id=user_id)
    assert summary['total_income'] > 0
    assert summary['total_expenses'] > 0
    assert summary['current_balance'] == round(summary['total_income'] - summary['total_expenses'], 2)
    assert summary['highest_expense_category'] != 'None'

    # 2. Category Analysis
    cat_analysis = analytics.get_category_analysis(user_id=user_id)
    assert len(cat_analysis) > 0
    total_pct = sum(c['percentage'] for c in cat_analysis)
    assert 98.0 <= total_pct <= 102.0

    # 3. Monthly Cashflow Analysis
    monthly = analytics.get_monthly_analysis(user_id=user_id)
    assert len(monthly) >= 3
    for m in monthly:
        assert m['savings'] == round(m['income'] - m['expense'], 2)

    # 4. Running Balance using NumPy cumsum
    running = analytics.get_running_balance(user_id=user_id)
    assert len(running) > 0
    final_balance = running[-1]['running_balance']
    assert final_balance == summary['current_balance']

    # 5. Spending Trend
    trend = analytics.get_spending_trend(user_id=user_id)
    assert len(trend['dates']) == len(trend['daily_expenses'])
    assert len(trend['dates']) == len(trend['cumulative_expenses'])

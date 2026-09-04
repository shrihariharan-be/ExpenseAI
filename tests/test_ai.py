import pytest
from services.ai_service import AIService
from services.budget_service import BudgetService

def test_ai_predictive_engine(db_service):
    budget_service = BudgetService(db_service)
    ai_service = AIService(db_service, budget_service=budget_service)
    user_id = 1

    # 1. Scikit-learn LinearRegression prediction & confidence metrics
    pred = ai_service.predict_next_month_expenses(user_id=user_id)
    assert 'predicted_total' in pred
    assert pred['predicted_total'] > 0
    assert pred['has_sufficient_data'] is True
    assert pred['trend_direction'] in ['increasing', 'decreasing', 'stable']
    assert 0.0 <= pred['r2_score'] <= 1.0
    assert 50.0 <= pred['confidence_score'] <= 100.0
    assert 'predicted_savings' in pred
    assert len(pred['category_predictions']) > 0
    assert 'trend_chart_data' in pred
    assert len(pred['trend_chart_data']['labels']) > 0

    # 2. Statistical Anomaly Detection (Z-Score & IQR)
    anomalies = ai_service.detect_unusual_spending(user_id=user_id)
    assert isinstance(anomalies, list)
    for a in anomalies:
        assert a['amount'] > a['mean_amount']
        assert a['multiplier'] >= 1.0
        assert 'z_score' in a
        assert 'detection_method' in a
        assert 'Z-Score' in a['detection_method'] or 'IQR' in a['detection_method']

    # 3. 5-Factor Financial Health Score Engine
    insights = ai_service.get_financial_insights(user_id=user_id)
    assert 'insights' in insights
    assert len(insights['insights']) > 0
    assert 0 <= insights['health_score'] <= 100
    assert 'sub_metrics' in insights
    
    sub = insights['sub_metrics']
    assert 'savings_rate' in sub
    assert 'budget_discipline' in sub
    assert 'expense_growth' in sub
    assert 'overspending_risk' in sub
    assert 'spending_consistency' in sub

    assert sub['savings_rate']['score'] <= 30
    assert sub['budget_discipline']['score'] <= 25
    assert sub['expense_growth']['score'] <= 20
    assert sub['overspending_risk']['score'] <= 15
    assert sub['spending_consistency']['score'] <= 10

    if insights['mom_comparison']:
        assert 'expense_diff' in insights['mom_comparison']
        assert 'current_savings' in insights['mom_comparison']

from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from config import Config

class AIService:
    def __init__(self, db_service, budget_service=None):
        self.db_service = db_service
        self.budget_service = budget_service

    def predict_next_month_expenses(self, user_id=None):
        """
        Uses Scikit-Learn LinearRegression on historical monthly data to forecast
        next month's total expenses, category-level allocations, savings forecast,
        and regression model confidence (R² score).
        """
        df = self.db_service.get_all_transactions_df(user_id=user_id)
        if df.empty:
            return {
                'predicted_total': 0.0,
                'predicted_savings': 0.0,
                'confidence_score': 0.0,
                'r2_score': 0.0,
                'trend_direction': 'stable',
                'trend_percentage': 0.0,
                'target_month': '',
                'category_predictions': [],
                'trend_chart_data': {'labels': [], 'actual': [], 'predicted': []},
                'has_sufficient_data': False
            }

        exp_df = df[df['type'] == 'Expense'].copy()
        inc_df = df[df['type'] == 'Income'].copy()

        if exp_df.empty:
            return {
                'predicted_total': 0.0,
                'predicted_savings': 0.0,
                'confidence_score': 0.0,
                'r2_score': 0.0,
                'trend_direction': 'stable',
                'trend_percentage': 0.0,
                'target_month': '',
                'category_predictions': [],
                'trend_chart_data': {'labels': [], 'actual': [], 'predicted': []},
                'has_sufficient_data': False
            }

        exp_df['month_key'] = exp_df['date'].dt.strftime('%Y-%m')
        exp_df['month_label'] = exp_df['date'].dt.strftime('%b %Y')
        monthly_exp = exp_df.groupby(['month_key', 'month_label'])['amount'].sum().reset_index()
        monthly_exp = monthly_exp.sort_values(by='month_key', ascending=True)

        # Average historical income for savings forecast
        avg_monthly_income = 0.0
        if not inc_df.empty:
            inc_df['month_key'] = inc_df['date'].dt.strftime('%Y-%m')
            monthly_inc = inc_df.groupby('month_key')['amount'].sum()
            avg_monthly_income = float(monthly_inc.mean())

        if len(monthly_exp) < 2:
            avg_expense = float(monthly_exp['amount'].mean())
            last_month = datetime.strptime(monthly_exp['month_key'].iloc[-1], '%Y-%m')
            next_month = (last_month + timedelta(days=32)).strftime('%B %Y')
            return {
                'predicted_total': round(avg_expense, 2),
                'predicted_savings': round(max(0.0, avg_monthly_income - avg_expense), 2),
                'confidence_score': 65.0,
                'r2_score': 0.50,
                'trend_direction': 'stable',
                'trend_percentage': 0.0,
                'target_month': next_month,
                'category_predictions': [],
                'trend_chart_data': {
                    'labels': monthly_exp['month_label'].tolist() + [next_month],
                    'actual': monthly_exp['amount'].round(2).tolist() + [None],
                    'predicted': [None] * len(monthly_exp) + [round(avg_expense, 2)]
                },
                'has_sufficient_data': False
            }

        # Train Scikit-Learn LinearRegression Model
        X = np.arange(len(monthly_exp)).reshape(-1, 1)
        y = monthly_exp['amount'].to_numpy(dtype=float)

        model = LinearRegression()
        model.fit(X, y)

        next_idx = np.array([[len(monthly_exp)]])
        predicted_val = float(model.predict(next_idx)[0])
        predicted_val = max(0.0, predicted_val)

        # Compute R² score (Coefficient of Determination)
        y_pred = model.predict(X)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2 = float(1 - (ss_res / ss_tot)) if ss_tot > 0 else 0.5
        r2 = max(0.0, min(1.0, r2))
        confidence_pct = round(60.0 + (r2 * 35.0), 1)

        # Direction & Change
        last_val = float(y[-1])
        pct_change = round(((predicted_val - last_val) / last_val) * 100, 1) if last_val > 0 else 0.0
        direction = 'increasing' if model.coef_[0] > 50 else ('decreasing' if model.coef_[0] < -50 else 'stable')

        last_month_dt = datetime.strptime(monthly_exp['month_key'].iloc[-1], '%Y-%m')
        year = last_month_dt.year + (1 if last_month_dt.month == 12 else 0)
        month = 1 if last_month_dt.month == 12 else last_month_dt.month + 1
        target_month_str = datetime(year, month, 1).strftime('%B %Y')

        # Savings Forecast
        predicted_savings = max(0.0, avg_monthly_income - predicted_val)

        # Category Allocation Forecast
        cat_share = exp_df.groupby('category')['amount'].sum()
        total_hist_exp = cat_share.sum()
        category_predictions = []

        for cat, amt in cat_share.items():
            share_pct = amt / total_hist_exp
            cat_predicted_amt = round(predicted_val * share_pct, 2)
            category_predictions.append({
                'category': cat,
                'predicted_amount': cat_predicted_amt,
                'percentage': round(share_pct * 100, 1),
                'color': Config.CATEGORY_COLORS.get(cat, '#64748B')
            })

        category_predictions.sort(key=lambda x: x['predicted_amount'], reverse=True)

        # Historical vs. Predicted Trend Line series for Chart.js
        trend_labels = monthly_exp['month_label'].tolist() + [target_month_str]
        actual_series = monthly_exp['amount'].round(2).tolist() + [None]
        # In predicted series, connect last actual point with the forecast
        predicted_series = [None] * (len(monthly_exp) - 1) + [round(float(y[-1]), 2), round(predicted_val, 2)]

        return {
            'predicted_total': round(predicted_val, 2),
            'predicted_savings': round(predicted_savings, 2),
            'confidence_score': confidence_pct,
            'r2_score': round(r2, 2),
            'trend_direction': direction,
            'trend_percentage': pct_change,
            'target_month': target_month_str,
            'category_predictions': category_predictions,
            'trend_chart_data': {
                'labels': trend_labels,
                'actual': actual_series,
                'predicted': predicted_series
            },
            'has_sufficient_data': True,
            'historical_months_count': len(monthly_exp)
        }

    def detect_unusual_spending(self, user_id=None):
        """
        Multi-Method Statistical Anomaly Detection:
        1. Z-score (z > 2.0)
        2. Interquartile Range / IQR Outlier (x > Q3 + 1.5*IQR)
        3. Mean + 2*Standard Deviation
        """
        df = self.db_service.get_all_transactions_df(user_id=user_id)
        if df.empty:
            return []

        exp_df = df[df['type'] == 'Expense'].copy()
        if len(exp_df) < 5:
            return []

        amounts = exp_df['amount'].to_numpy(dtype=float)
        mean_amt = float(np.mean(amounts))
        std_amt = float(np.std(amounts))

        q25 = float(np.percentile(amounts, 25))
        q75 = float(np.percentile(amounts, 75))
        iqr = q75 - q25
        iqr_threshold = q75 + (1.5 * iqr)
        z_threshold = 2.0

        results = []
        for _, row in exp_df.iterrows():
            amt = float(row['amount'])
            z_score = (amt - mean_amt) / std_amt if std_amt > 0 else 0.0

            is_z_anomaly = z_score >= z_threshold
            is_iqr_anomaly = amt > iqr_threshold

            if is_z_anomaly or is_iqr_anomaly:
                multiplier = round(amt / mean_amt, 1) if mean_amt > 0 else 1.0
                method = "Z-Score (> 2.0) & IQR" if (is_z_anomaly and is_iqr_anomaly) else ("Z-Score (> 2.0)" if is_z_anomaly else "IQR Outlier")
                
                results.append({
                    'id': int(row['id']),
                    'date': row['date'].strftime('%Y-%m-%d'),
                    'category': row['category'],
                    'description': row['description'] or 'No description',
                    'amount': round(amt, 2),
                    'mean_amount': round(mean_amt, 2),
                    'z_score': round(z_score, 2),
                    'multiplier': multiplier,
                    'detection_method': method,
                    'color': Config.CATEGORY_COLORS.get(row['category'], '#64748B'),
                    'explanation': f"Transaction amount is {multiplier}x the typical average expense of ₹{mean_amt:,.2f}."
                })

        results.sort(key=lambda x: x['amount'], reverse=True)
        return results

    def get_financial_insights(self, user_id=None):
        """
        Calculates Multi-Factor Financial Health Score (0–100) across 5 parameters:
        1. Savings Rate (30 pts)
        2. Budget Discipline (25 pts)
        3. Expense Growth & Velocity (20 pts)
        4. Overspending Risk (15 pts)
        5. Daily Spending Stability / Consistency (10 pts)
        """
        df = self.db_service.get_all_transactions_df(user_id=user_id)
        insights = []

        if df.empty:
            return {
                'insights': ["No financial activity recorded yet. Start by logging your transactions!"],
                'mom_comparison': None,
                'health_score': 50,
                'rating': 'New Account',
                'sub_metrics': {
                    'savings_rate': {'score': 15, 'max': 30, 'rating': 'New Account', 'value': '0%'},
                    'budget_discipline': {'score': 15, 'max': 25, 'rating': 'Not Configured', 'value': 'N/A'},
                    'expense_growth': {'score': 10, 'max': 20, 'rating': 'Stable', 'value': '0%'},
                    'overspending_risk': {'score': 10, 'max': 15, 'rating': 'Low', 'value': 'None'},
                    'spending_consistency': {'score': 5, 'max': 10, 'rating': 'Moderate', 'value': 'N/A'}
                }
            }

        df['month_key'] = df['date'].dt.strftime('%Y-%m')
        unique_months = sorted(df['month_key'].unique().tolist())

        mom_data = None
        exp_pct_change = 0.0

        if len(unique_months) >= 2:
            current_m = unique_months[-1]
            prev_m = unique_months[-2]

            curr_df = df[df['month_key'] == current_m]
            prev_df = df[df['month_key'] == prev_m]

            curr_inc = float(curr_df[curr_df['type'] == 'Income']['amount'].sum())
            curr_exp = float(curr_df[curr_df['type'] == 'Expense']['amount'].sum())
            prev_inc = float(prev_df[prev_df['type'] == 'Income']['amount'].sum())
            prev_exp = float(prev_df[prev_df['type'] == 'Expense']['amount'].sum())

            curr_savings = curr_inc - curr_exp
            prev_savings = prev_inc - prev_exp

            exp_diff = curr_exp - prev_exp
            exp_pct_change = round(((curr_exp - prev_exp) / prev_exp) * 100, 1) if prev_exp > 0 else 0.0

            inc_diff = curr_inc - prev_inc
            inc_pct = round(((curr_inc - prev_inc) / prev_inc) * 100, 1) if prev_inc > 0 else 0.0

            mom_data = {
                'current_month': datetime.strptime(current_m, '%Y-%m').strftime('%B %Y'),
                'prev_month': datetime.strptime(prev_m, '%Y-%m').strftime('%B %Y'),
                'current_income': curr_inc,
                'prev_income': prev_inc,
                'current_expense': curr_exp,
                'prev_expense': prev_exp,
                'expense_diff': exp_diff,
                'expense_pct': exp_pct_change,
                'income_diff': inc_diff,
                'income_pct': inc_pct,
                'current_savings': curr_savings,
                'prev_savings': prev_savings
            }

            if exp_diff > 0:
                insights.append({
                    'type': 'warning',
                    'icon': 'fa-solid fa-arrow-trend-up',
                    'title': 'Monthly Spending Increase',
                    'text': f"Your expenses increased by ₹{abs(exp_diff):,.2f} ({abs(exp_pct_change)}%) in {mom_data['current_month']} compared to {mom_data['prev_month']}."
                })
            else:
                insights.append({
                    'type': 'success',
                    'icon': 'fa-solid fa-arrow-trend-down',
                    'title': 'Monthly Expense Savings',
                    'text': f"You reduced your monthly expenses by ₹{abs(exp_diff):,.2f} ({abs(exp_pct_change)}%) compared to last month."
                })

            # Check category surges
            curr_cat = curr_df[curr_df['type'] == 'Expense'].groupby('category')['amount'].sum()
            prev_cat = prev_df[prev_df['type'] == 'Expense'].groupby('category')['amount'].sum()

            for cat in curr_cat.index:
                c_amt = float(curr_cat[cat])
                p_amt = float(prev_cat.get(cat, 0.0))
                if p_amt > 0:
                    pct = round(((c_amt - p_amt) / p_amt) * 100, 1)
                    if pct >= 20.0:
                        insights.append({
                            'type': 'info',
                            'icon': 'fa-solid fa-chart-line',
                            'title': f'{cat} Category Spike',
                            'text': f"Your {cat} spending increased by {pct}% (₹{c_amt:,.2f} vs ₹{p_amt:,.2f}) compared to last month."
                        })

        # --- 5-FACTOR FINANCIAL HEALTH SCORE CALCULATION ---
        total_inc = float(df[df['type'] == 'Income']['amount'].sum())
        total_exp = float(df[df['type'] == 'Expense']['amount'].sum())
        savings_rate = round(((total_inc - total_exp) / total_inc) * 100, 1) if total_inc > 0 else 0.0

        # 1. Savings Rate Score (Max 30)
        if savings_rate >= 35.0:
            savings_score = 30
            savings_rating = 'Excellent'
        elif savings_rate >= 20.0:
            savings_score = 24
            savings_rating = 'Good'
        elif savings_rate >= 10.0:
            savings_score = 16
            savings_rating = 'Moderate'
        elif savings_rate >= 0.0:
            savings_score = 8
            savings_rating = 'Low'
        else:
            savings_score = 0
            savings_rating = 'Deficit'

        # 2. Budget Discipline Score (Max 25)
        budget_adherence_score = 20
        budget_rating = 'Good'
        if self.budget_service:
            b_status = self.budget_service.get_budget_status(user_id=user_id)
            if b_status and b_status['total_budget'] > 0:
                pct = b_status['overall_percentage']
                if pct <= 75.0:
                    budget_adherence_score = 25
                    budget_rating = 'Excellent'
                elif pct <= 90.0:
                    budget_adherence_score = 20
                    budget_rating = 'Good'
                elif pct <= 100.0:
                    budget_adherence_score = 14
                    budget_rating = 'Approaching Limit'
                else:
                    budget_adherence_score = 5
                    budget_rating = 'Overbudget'

        # 3. Expense Growth Score (Max 20)
        if exp_pct_change <= -5.0:
            growth_score = 20
            growth_rating = 'Controlled'
        elif exp_pct_change <= 5.0:
            growth_score = 17
            growth_rating = 'Stable'
        elif exp_pct_change <= 20.0:
            growth_score = 11
            growth_rating = 'Moderate'
        else:
            growth_score = 4
            growth_rating = 'Surging'

        # 4. Overspending Risk Score (Max 15)
        # Ratio of expenses to income
        exp_inc_ratio = (total_exp / total_inc) if total_inc > 0 else 1.0
        if exp_inc_ratio <= 0.6:
            risk_score = 15
            risk_rating = 'Low'
        elif exp_inc_ratio <= 0.8:
            risk_score = 11
            risk_rating = 'Moderate'
        else:
            risk_score = 4
            risk_rating = 'High'

        # 5. Spending Consistency Score (Max 10)
        exp_df = df[df['type'] == 'Expense']
        if len(exp_df) >= 4:
            amounts = exp_df['amount'].to_numpy(dtype=float)
            cv = np.std(amounts) / np.mean(amounts) if np.mean(amounts) > 0 else 1.0
            if cv < 1.0:
                cons_score = 10
                cons_rating = 'High'
            elif cv < 1.8:
                cons_score = 7
                cons_rating = 'Moderate'
            else:
                cons_score = 4
                cons_rating = 'Volatile'
        else:
            cons_score = 7
            cons_rating = 'Moderate'

        total_health_score = int(savings_score + budget_adherence_score + growth_score + risk_score + cons_score)
        total_health_score = max(10, min(100, total_health_score))

        if total_health_score >= 85:
            overall_rating = 'Excellent 🌟'
        elif total_health_score >= 70:
            overall_rating = 'Good 👍'
        elif total_health_score >= 50:
            overall_rating = 'Fair ⚖️'
        else:
            overall_rating = 'Needs Attention ⚠️'

        insights.append({
            'type': 'primary',
            'icon': 'fa-solid fa-piggy-bank',
            'title': 'Savings & Inflow Strength',
            'text': f"Your overall savings rate stands at {savings_rate}%, which is rated {savings_rating}."
        })

        sub_metrics = {
            'savings_rate': {'score': savings_score, 'max': 30, 'rating': savings_rating, 'value': f"{savings_rate}%"},
            'budget_discipline': {'score': budget_adherence_score, 'max': 25, 'rating': budget_rating, 'value': f"{budget_adherence_score}/25"},
            'expense_growth': {'score': growth_score, 'max': 20, 'rating': growth_rating, 'value': f"{'+' if exp_pct_change >= 0 else ''}{exp_pct_change}%"},
            'overspending_risk': {'score': risk_score, 'max': 15, 'rating': risk_rating, 'value': risk_rating},
            'spending_consistency': {'score': cons_score, 'max': 10, 'rating': cons_rating, 'value': cons_rating}
        }

        return {
            'insights': insights,
            'mom_comparison': mom_data,
            'health_score': total_health_score,
            'savings_rate': savings_rate,
            'rating': overall_rating,
            'sub_metrics': sub_metrics
        }

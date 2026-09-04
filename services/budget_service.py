from datetime import datetime
import pandas as pd
from config import Config

class BudgetService:
    def __init__(self, db_service):
        self.db_service = db_service

    def set_budget(self, user_id, category, monthly_budget, month_year=None):
        """
        Creates or updates a monthly budget for a specific category.
        """
        if category not in Config.EXPENSE_CATEGORIES:
            raise ValueError(f"Invalid expense category: {category}")

        try:
            val = float(monthly_budget)
            if val <= 0:
                raise ValueError("Monthly budget must be greater than zero.")
        except (TypeError, ValueError):
            raise ValueError("Please provide a valid positive budget amount.")

        month_year = month_year or datetime.now().strftime('%Y-%m')

        with self.db_service.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO budgets (user_id, category, monthly_budget, month_year)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, category, month_year) DO UPDATE SET
                    monthly_budget = excluded.monthly_budget,
                    created_at = CURRENT_TIMESTAMP
            ''', (user_id, category, round(val, 2), month_year))
            conn.commit()
            return cursor.lastrowid

    def delete_budget(self, budget_id, user_id):
        with self.db_service.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM budgets WHERE id = ? AND user_id = ?', (budget_id, user_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_user_budgets(self, user_id, month_year=None):
        month_year = month_year or datetime.now().strftime('%Y-%m')
        with self.db_service.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM budgets
                WHERE user_id = ? AND month_year = ?
                ORDER BY category ASC
            ''', (user_id, month_year))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_budget_status(self, user_id, month_year=None):
        """
        Calculates spending vs budget for each category for a given month.
        Generates alerts for approaching/exceeded limits.
        """
        month_year = month_year or datetime.now().strftime('%Y-%m')
        budgets = self.get_user_budgets(user_id, month_year)

        # Get actual expenses for that month using DataFrame
        df = self.db_service.get_all_transactions_df(user_id=user_id)
        month_expenses = {}

        if not df.empty:
            df['month_key'] = df['date'].dt.strftime('%Y-%m')
            exp_df = df[(df['month_key'] == month_year) & (df['type'] == 'Expense')]
            if not exp_df.empty:
                cat_grouped = exp_df.groupby('category')['amount'].sum().to_dict()
                month_expenses = {k: float(v) for k, v in cat_grouped.items()}

        category_statuses = []
        total_budget = 0.0
        total_spent = 0.0
        alerts = []

        for b in budgets:
            cat = b['category']
            b_amount = float(b['monthly_budget'])
            spent = float(month_expenses.get(cat, 0.0))
            remaining = b_amount - spent
            pct = round((spent / b_amount) * 100, 1) if b_amount > 0 else 0.0

            total_budget += b_amount
            total_spent += spent

            if spent > b_amount:
                status = 'exceeded'
                overspent = round(spent - b_amount, 2)
                alerts.append({
                    'type': 'danger',
                    'category': cat,
                    'message': f"Overbudget Alert: {cat} spending (₹{spent:,.2f}) has exceeded budget (₹{b_amount:,.2f}) by ₹{overspent:,.2f}!"
                })
            elif pct >= 80.0:
                status = 'warning'
                alerts.append({
                    'type': 'warning',
                    'category': cat,
                    'message': f"Budget Warning: {cat} is at {pct}% of your ₹{b_amount:,.2f} monthly limit."
                })
            else:
                status = 'safe'

            category_statuses.append({
                'id': b['id'],
                'category': cat,
                'budget': b_amount,
                'spent': round(spent, 2),
                'remaining': round(remaining, 2),
                'percentage': min(100.0, pct),
                'raw_percentage': pct,
                'status': status,
                'color': Config.CATEGORY_COLORS.get(cat, '#64748B')
            })

        # Overall monthly budget calculation
        overall_remaining = round(total_budget - total_spent, 2)
        overall_pct = round((total_spent / total_budget) * 100, 1) if total_budget > 0 else 0.0

        return {
            'month_year': month_year,
            'month_label': datetime.strptime(month_year, '%Y-%m').strftime('%B %Y'),
            'total_budget': round(total_budget, 2),
            'total_spent': round(total_spent, 2),
            'total_remaining': overall_remaining,
            'overall_percentage': min(100.0, overall_pct),
            'categories': category_statuses,
            'alerts': alerts
        }

import numpy as np
import pandas as pd
from datetime import datetime
from config import Config

class AnalyticsService:
    def __init__(self, db_service):
        self.db_service = db_service

    def get_summary_metrics(self, df=None, user_id=None):
        """
        Calculates high-level metrics using Pandas and NumPy:
        Total Income, Total Expenses, Current Balance, Average Daily Expense,
        Highest Expense Category, and Transaction Counts.
        """
        if df is None:
            df = self.db_service.get_all_transactions_df(user_id=user_id)

        if df.empty:
            return {
                'total_income': 0.0,
                'total_expenses': 0.0,
                'current_balance': 0.0,
                'avg_daily_expense': 0.0,
                'highest_expense_category': 'None',
                'highest_expense_amount': 0.0,
                'total_transactions': 0,
                'income_count': 0,
                'expense_count': 0
            }

        income_mask = df['type'] == 'Income'
        expense_mask = df['type'] == 'Expense'

        total_income = float(df.loc[income_mask, 'amount'].sum())
        total_expenses = float(df.loc[expense_mask, 'amount'].sum())
        current_balance = float(total_income - total_expenses)

        income_count = int(income_mask.sum())
        expense_count = int(expense_mask.sum())
        total_transactions = int(len(df))

        # Highest spending category
        expenses_df = df[expense_mask]
        if not expenses_df.empty:
            cat_sum = expenses_df.groupby('category')['amount'].sum()
            highest_cat = cat_sum.idxmax()
            highest_cat_amt = float(cat_sum.max())

            min_date = expenses_df['date'].min()
            max_date = expenses_df['date'].max()
            num_days = max(1, (max_date - min_date).days + 1)
            avg_daily_expense = float(np.round(total_expenses / num_days, 2))
        else:
            highest_cat = 'None'
            highest_cat_amt = 0.0
            avg_daily_expense = 0.0

        return {
            'total_income': round(total_income, 2),
            'total_expenses': round(total_expenses, 2),
            'current_balance': round(current_balance, 2),
            'avg_daily_expense': round(avg_daily_expense, 2),
            'highest_expense_category': highest_cat,
            'highest_expense_amount': round(highest_cat_amt, 2),
            'total_transactions': total_transactions,
            'income_count': income_count,
            'expense_count': expense_count
        }

    def get_category_analysis(self, df=None, user_id=None):
        """
        Category-wise spending and percentage calculation using Pandas.
        Returns sorted list of dicts with Category, Amount, Percentage, Color.
        """
        if df is None:
            df = self.db_service.get_all_transactions_df(user_id=user_id)

        if df.empty:
            return []

        expenses_df = df[df['type'] == 'Expense']
        if expenses_df.empty:
            return []

        total_expense = expenses_df['amount'].sum()
        if total_expense == 0:
            return []

        cat_summary = expenses_df.groupby('category')['amount'].sum().reset_index()
        cat_summary['percentage'] = (cat_summary['amount'] / total_expense * 100).round(2)
        cat_summary = cat_summary.sort_values(by='amount', ascending=False)

        results = []
        for _, row in cat_summary.iterrows():
            cat_name = str(row['category'])
            results.append({
                'category': cat_name,
                'amount': round(float(row['amount']), 2),
                'percentage': round(float(row['percentage']), 2),
                'color': Config.CATEGORY_COLORS.get(cat_name, '#64748B')
            })

        return results

    def get_monthly_analysis(self, df=None, user_id=None):
        """
        Calculates Monthly Income, Expenses, and Savings using Pandas groupby/pivot.
        Returns sorted list of monthly stats for tables and charts.
        """
        if df is None:
            df = self.db_service.get_all_transactions_df(user_id=user_id)

        if df.empty:
            return []

        df_copy = df.copy()
        df_copy['month_key'] = df_copy['date'].dt.strftime('%Y-%m')
        df_copy['month_label'] = df_copy['date'].dt.strftime('%b %Y')

        grouped = df_copy.groupby(['month_key', 'month_label', 'type'])['amount'].sum().unstack(fill_value=0.0).reset_index()

        if 'Income' not in grouped.columns:
            grouped['Income'] = 0.0
        if 'Expense' not in grouped.columns:
            grouped['Expense'] = 0.0

        grouped['Savings'] = grouped['Income'] - grouped['Expense']
        grouped = grouped.sort_values(by='month_key', ascending=True)

        results = []
        for _, row in grouped.iterrows():
            results.append({
                'month_key': row['month_key'],
                'month_label': row['month_label'],
                'income': round(float(row['Income']), 2),
                'expense': round(float(row['Expense']), 2),
                'savings': round(float(row['Savings']), 2)
            })

        return results

    def get_running_balance(self, df=None, user_id=None):
        """
        Calculates Running Balance using NumPy vectorization and np.cumsum().
        """
        if df is None:
            df = self.db_service.get_all_transactions_df(user_id=user_id)

        if df.empty:
            return []

        df_sorted = df.sort_values(by=['date', 'id'], ascending=True).copy()

        amounts = df_sorted['amount'].to_numpy(dtype=float)
        is_income = (df_sorted['type'] == 'Income').to_numpy()
        signed_amounts = np.where(is_income, amounts, -amounts)
        running_balances = np.cumsum(signed_amounts)

        df_sorted['running_balance'] = running_balances

        records = []
        for _, row in df_sorted.iterrows():
            records.append({
                'id': int(row['id']),
                'date': row['date'].strftime('%Y-%m-%d'),
                'type': row['type'],
                'category': row['category'],
                'description': row['description'],
                'amount': round(float(row['amount']), 2),
                'running_balance': round(float(row['running_balance']), 2)
            })

        return records

    def get_spending_trend(self, df=None, user_id=None):
        """
        Calculates daily spending trend and cumulative spending for Chart.js.
        """
        if df is None:
            df = self.db_service.get_all_transactions_df(user_id=user_id)

        if df.empty:
            return {'dates': [], 'daily_expenses': [], 'cumulative_expenses': []}

        expenses_df = df[df['type'] == 'Expense'].copy()
        if expenses_df.empty:
            return {'dates': [], 'daily_expenses': [], 'cumulative_expenses': []}

        expenses_df['date_str'] = expenses_df['date'].dt.strftime('%Y-%m-%d')
        daily_expense = expenses_df.groupby('date_str')['amount'].sum().reset_index()
        daily_expense = daily_expense.sort_values(by='date_str', ascending=True)

        amounts = daily_expense['amount'].to_numpy(dtype=float)
        cumulative = np.cumsum(amounts)

        return {
            'dates': daily_expense['date_str'].tolist(),
            'daily_expenses': [round(float(a), 2) for a in amounts],
            'cumulative_expenses': [round(float(c), 2) for c in cumulative]
        }

    def get_dashboard_data(self, user_id=None):
        """
        Aggregates all metrics and chart payloads for the main dashboard.
        """
        df = self.db_service.get_all_transactions_df(user_id=user_id)
        summary = self.get_summary_metrics(df, user_id=user_id)
        cat_data = self.get_category_analysis(df, user_id=user_id)
        monthly_data = self.get_monthly_analysis(df, user_id=user_id)
        trend_data = self.get_spending_trend(df, user_id=user_id)

        # Recent transactions scoped by user
        recent_txs = self.db_service.get_transactions(user_id=user_id, limit=8)

        # Current month metrics
        current_month_key = datetime.now().strftime('%Y-%m')
        current_monthly_stat = next((m for m in monthly_data if m['month_key'] == current_month_key), None)
        monthly_income = current_monthly_stat['income'] if current_monthly_stat else 0.0
        monthly_expenses = current_monthly_stat['expense'] if current_monthly_stat else 0.0

        return {
            'summary': summary,
            'monthly_income': monthly_income,
            'monthly_expenses': monthly_expenses,
            'recent_transactions': recent_txs,
            'category_chart': {
                'labels': [c['category'] for c in cat_data],
                'data': [c['amount'] for c in cat_data],
                'colors': [c['color'] for c in cat_data]
            },
            'monthly_chart': {
                'labels': [m['month_label'] for m in monthly_data],
                'income': [m['income'] for m in monthly_data],
                'expenses': [m['expense'] for m in monthly_data],
                'savings': [m['savings'] for m in monthly_data]
            },
            'spending_trend': trend_data
        }

    def get_report_data(self, user_id=None, period_type='monthly', start_date=None, end_date=None):
        """
        Generates analytics and transactions for specified time horizons:
        daily, weekly, monthly, or custom range.
        """
        today = pd.Timestamp.now().normalize()

        if period_type == 'daily':
            start = today
            end = today
        elif period_type == 'weekly':
            start = today - pd.Timedelta(days=6)
            end = today
        elif period_type == 'monthly':
            start = today.replace(day=1)
            end = today
        elif period_type == 'custom':
            start = pd.to_datetime(start_date) if start_date else None
            end = pd.to_datetime(end_date) if end_date else None
        else:
            start = None
            end = None

        df = self.db_service.get_all_transactions_df(user_id=user_id)
        if not df.empty and start is not None:
            df = df[df['date'] >= start]
        if not df.empty and end is not None:
            end_bound = end + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
            df = df[df['date'] <= end_bound]

        summary = self.get_summary_metrics(df, user_id=user_id)
        categories = self.get_category_analysis(df, user_id=user_id)
        monthly = self.get_monthly_analysis(df, user_id=user_id)

        if df.empty:
            transactions = []
        else:
            df_display = df.sort_values(by=['date', 'id'], ascending=[False, False]).copy()
            df_display['date'] = df_display['date'].dt.strftime('%Y-%m-%d')
            transactions = df_display.to_dict('records')

        return {
            'period_type': period_type,
            'start_date': start.strftime('%Y-%m-%d') if start is not None else '',
            'end_date': end.strftime('%Y-%m-%d') if end is not None else '',
            'summary': summary,
            'categories': categories,
            'monthly': monthly,
            'transactions': transactions
        }

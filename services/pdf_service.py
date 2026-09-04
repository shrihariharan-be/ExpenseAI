import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

class PDFReportService:
    def __init__(self, analytics_service, db_service):
        self.analytics_service = analytics_service
        self.db_service = db_service

    def generate_financial_pdf(self, user_id=None, username="User", period_type="all"):
        """
        Generates a professional financial statement in PDF format using ReportLab.
        Returns a BytesIO buffer.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        elements = []
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=20,
            textColor=colors.HexColor('#1E293B'),
            spaceAfter=4
        )
        subtitle_style = ParagraphStyle(
            'DocSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            textColor=colors.HexColor('#64748B'),
            spaceAfter=12
        )
        h2_style = ParagraphStyle(
            'H2',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=13,
            textColor=colors.HexColor('#2563EB'),
            spaceBefore=10,
            spaceAfter=6
        )
        body_style = ParagraphStyle(
            'Body',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            textColor=colors.HexColor('#334155')
        )
        body_bold = ParagraphStyle(
            'BodyBold',
            parent=body_style,
            fontName='Helvetica-Bold'
        )

        # 1. Document Header
        elements.append(Paragraph("Personal Expense Tracker & Financial Statement", title_style))
        now_str = datetime.now().strftime('%B %d, %Y - %I:%M %p')
        elements.append(Paragraph(f"Account: <b>{username}</b> | Statement Generated: {now_str} | Scope: {period_type.capitalize()}", subtitle_style))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=14))

        # 2. Executive Financial Summary
        df = self.db_service.get_all_transactions_df(user_id=user_id)
        summary = self.analytics_service.get_summary_metrics(df)

        elements.append(Paragraph("Executive Financial Summary", h2_style))
        summary_data = [
            [
                Paragraph("<b>Total Income</b>", body_style),
                Paragraph(f"<font color='#16A34A'><b>+INR {summary['total_income']:,.2f}</b></font>", body_bold),
                Paragraph("<b>Total Expenses</b>", body_style),
                Paragraph(f"<font color='#DC2626'><b>-INR {summary['total_expenses']:,.2f}</b></font>", body_bold)
            ],
            [
                Paragraph("<b>Net Balance</b>", body_style),
                Paragraph(f"<font color='#2563EB'><b>INR {summary['current_balance']:,.2f}</b></font>", body_bold),
                Paragraph("<b>Avg Daily Burn</b>", body_style),
                Paragraph(f"INR {summary['avg_daily_expense']:,.2f}", body_style)
            ],
            [
                Paragraph("<b>Top Spending Category</b>", body_style),
                Paragraph(f"<b>{summary['highest_expense_category']}</b> (INR {summary['highest_expense_amount']:,.2f})", body_style),
                Paragraph("<b>Transactions Count</b>", body_style),
                Paragraph(f"{summary['total_transactions']} records", body_style)
            ]
        ]
        summary_table = Table(summary_data, colWidths=[1.8*inch, 2.0*inch, 1.8*inch, 1.8*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#E2E8F0')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 14))

        # 3. Category Spending Breakdown
        cat_data = self.analytics_service.get_category_analysis(df)
        if cat_data:
            elements.append(Paragraph("Category Spending Breakdown", h2_style))
            cat_table_data = [[
                Paragraph("<b>Category</b>", body_bold),
                Paragraph("<b>Amount (INR)</b>", body_bold),
                Paragraph("<b>Share (%)</b>", body_bold)
            ]]
            for c in cat_data[:8]:
                cat_table_data.append([
                    Paragraph(c['category'], body_style),
                    Paragraph(f"INR {c['amount']:,.2f}", body_style),
                    Paragraph(f"{c['percentage']}%", body_style)
                ])
            cat_table = Table(cat_table_data, colWidths=[2.5*inch, 2.5*inch, 2.4*inch])
            cat_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(cat_table)
            elements.append(Spacer(1, 14))

        # 4. Monthly Cashflow History
        monthly_data = self.analytics_service.get_monthly_analysis(df)
        if monthly_data:
            elements.append(Paragraph("Monthly Cashflow Performance", h2_style))
            month_table_data = [[
                Paragraph("<b>Month</b>", body_bold),
                Paragraph("<b>Income (INR)</b>", body_bold),
                Paragraph("<b>Expense (INR)</b>", body_bold),
                Paragraph("<b>Net Savings (INR)</b>", body_bold)
            ]]
            for m in monthly_data:
                month_table_data.append([
                    Paragraph(m['month_label'], body_style),
                    Paragraph(f"<font color='#16A34A'>+{m['income']:,.2f}</font>", body_style),
                    Paragraph(f"<font color='#DC2626'>-{m['expense']:,.2f}</font>", body_style),
                    Paragraph(f"<b>{'+' if m['savings'] >= 0 else ''}{m['savings']:,.2f}</b>", body_style)
                ])
            month_table = Table(month_table_data, colWidths=[2.0*inch, 1.8*inch, 1.8*inch, 1.8*inch])
            month_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(month_table)
            elements.append(Spacer(1, 14))

        # 5. Footer note
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CBD5E1'), spaceAfter=8))
        elements.append(Paragraph("Personal Expense Tracker & AI-Powered Financial Analytics System — Confidential Financial Document", subtitle_style))

        doc.build(elements)
        buffer.seek(0)
        return buffer

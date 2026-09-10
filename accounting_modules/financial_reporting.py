"""
Financial Reporting Engine (GAAP / IFRS Compliance)
Generates Balance Sheet, Income Statement (P&L), and Statement of Cash Flows
from normalized trial balances and ledger transactions.
"""

class FinancialReportingEngine:
    def __init__(self, company_name="Client Entity"):
        self.company_name = company_name

    def generate_income_statement(self, revenues: dict, expenses: dict) -> dict:
        total_revenue = sum(revenues.values())
        total_expenses = sum(expenses.values())
        net_income = total_revenue - total_expenses
        return {
            "statement": "Income Statement",
            "company": self.company_name,
            "revenues": revenues,
            "total_revenue": total_revenue,
            "expenses": expenses,
            "total_expenses": total_expenses,
            "net_income": net_income
        }

    def generate_balance_sheet(self, assets: dict, liabilities: dict, equity: dict, net_income: float) -> dict:
        total_assets = sum(assets.values())
        total_liabilities = sum(liabilities.values())
        
        adjusted_equity = equity.copy()
        adjusted_equity["Net Income (Current Period)"] = net_income
        total_equity = sum(adjusted_equity.values())
        
        balanced = abs(total_assets - (total_liabilities + total_equity)) < 0.01
        
        return {
            "statement": "Balance Sheet",
            "company": self.company_name,
            "assets": assets,
            "total_assets": total_assets,
            "liabilities": liabilities,
            "total_liabilities": total_liabilities,
            "equity": adjusted_equity,
            "total_equity": total_equity,
            "liabilities_plus_equity": total_liabilities + total_equity,
            "is_balanced": balanced
        }

if __name__ == "__main__":
    fre = FinancialReportingEngine("Acme Corp")
    rev = {"Service Revenue": 150000.0, "Product Revenue": 50000.0}
    exp = {"Cost of Goods Sold": 60000.0, "Salaries Expense": 50000.0, "Rent Expense": 12000.0}
    inc = fre.generate_income_statement(rev, exp)
    print("Income Statement Net Income:", inc["net_income"])

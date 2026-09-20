"""
Financial Reporting Engine (GAAP / IFRS Compliance)
Generates Balance Sheet, Income Statement (P&L), Statement of Retained Earnings,
and Statement of Cash Flows from normalized trial balances and ledger transactions.
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
            "total_revenue": round(total_revenue, 2),
            "expenses": expenses,
            "total_expenses": round(total_expenses, 2),
            "net_income": round(net_income, 2)
        }

    def generate_income_statement_from_ledger(self, bookkeeping_engine) -> dict:
        revenues = {}
        expenses = {}
        
        # Get adjusted trial balance
        tb, _, _ = bookkeeping_engine.get_trial_balance(trial_balance_type="adjusted")
        
        for acc, props in bookkeeping_engine.accounts.items():
            if acc in tb:
                val = tb[acc]["debit"] if props["normal"] == "Debit" else tb[acc]["credit"]
                if props["type"] == "Revenue":
                    revenues[acc] = val
                elif props["type"] == "Expense":
                    expenses[acc] = val
                    
        return self.generate_income_statement(revenues, expenses)

    def generate_balance_sheet(self, assets: dict, liabilities: dict, equity: dict, net_income: float, is_already_closed: bool = False) -> dict:
        total_assets = sum(assets.values())
        total_liabilities = sum(liabilities.values())
        
        adjusted_equity = equity.copy()
        if not is_already_closed:
            # If not closed, Net Income must be added to equity to balance
            adjusted_equity["Net Income (Current Period)"] = net_income
            
        total_equity = sum(adjusted_equity.values())
        balanced = abs(total_assets - (total_liabilities + total_equity)) < 0.01
        
        return {
            "statement": "Balance Sheet",
            "company": self.company_name,
            "assets": assets,
            "total_assets": round(total_assets, 2),
            "liabilities": liabilities,
            "total_liabilities": round(total_liabilities, 2),
            "equity": adjusted_equity,
            "total_equity": round(total_equity, 2),
            "liabilities_plus_equity": round(total_liabilities + total_equity, 2),
            "is_balanced": balanced
        }

    def generate_balance_sheet_from_ledger(self, bookkeeping_engine) -> dict:
        assets = {}
        liabilities = {}
        equity = {}
        
        # If closed, we use post-closing trial balance, otherwise adjusted
        tb_type = "post-closing" if bookkeeping_engine.is_closed else "adjusted"
        tb, _, _ = bookkeeping_engine.get_trial_balance(trial_balance_type=tb_type)
        
        for acc, props in bookkeeping_engine.accounts.items():
            if acc in tb:
                val = tb[acc]["debit"] if props["normal"] == "Debit" else tb[acc]["credit"]
                if props["type"] == "Asset":
                    assets[acc] = val
                elif props["type"] == "Liability":
                    liabilities[acc] = val
                elif props["type"] == "Equity":
                    equity[acc] = val
                    
        # Calculate net income if not closed
        net_income = 0.0
        if not bookkeeping_engine.is_closed:
            inc_stmt = self.generate_income_statement_from_ledger(bookkeeping_engine)
            net_income = inc_stmt["net_income"]
            
        return self.generate_balance_sheet(assets, liabilities, equity, net_income, is_already_closed=bookkeeping_engine.is_closed)

    def generate_statement_of_retained_earnings(self, beginning_retained_earnings: float, net_income: float, dividends: float) -> dict:
        ending_retained_earnings = beginning_retained_earnings + net_income - dividends
        return {
            "statement": "Statement of Retained Earnings",
            "company": self.company_name,
            "beginning_retained_earnings": round(beginning_retained_earnings, 2),
            "net_income": round(net_income, 2),
            "dividends": round(dividends, 2),
            "ending_retained_earnings": round(ending_retained_earnings, 2)
        }

    def generate_cash_flow_statement(
        self, 
        net_income: float, 
        non_cash_adjustments: dict, 
        working_capital_changes: dict, 
        investing_activities: dict, 
        financing_activities: dict, 
        beginning_cash: float
    ) -> dict:
        """
        Generates Statement of Cash Flows using the Indirect Method.
        non_cash_adjustments: e.g., {"Depreciation Expense": 5000.0} (added back to net income)
        working_capital_changes: e.g., {"Increase in Accounts Receivable": -2000.0, "Increase in Accounts Payable": 1500.0}
        investing_activities: e.g., {"Purchase of Equipment": -10000.0}
        financing_activities: e.g., {"Issuance of Common Stock": 20000.0, "Payment of Dividends": -5000.0}
        """
        # Operating Activities
        total_non_cash = sum(non_cash_adjustments.values())
        total_wc_changes = sum(working_capital_changes.values())
        cash_from_operating = net_income + total_non_cash + total_wc_changes
        
        # Investing Activities
        cash_from_investing = sum(investing_activities.values())
        
        # Financing Activities
        cash_from_financing = sum(financing_activities.values())
        
        # Net Change and Ending Cash
        net_change = cash_from_operating + cash_from_investing + cash_from_financing
        ending_cash = beginning_cash + net_change
        
        return {
            "statement": "Statement of Cash Flows (Indirect Method)",
            "company": self.company_name,
            "operating_activities": {
                "net_income": round(net_income, 2),
                "non_cash_adjustments": non_cash_adjustments,
                "working_capital_changes": working_capital_changes,
                "net_cash_provided_by_operating": round(cash_from_operating, 2)
            },
            "investing_activities": {
                "items": investing_activities,
                "net_cash_used_in_investing": round(cash_from_investing, 2)
            },
            "financing_activities": {
                "items": financing_activities,
                "net_cash_provided_by_financing": round(cash_from_financing, 2)
            },
            "net_increase_in_cash": round(net_change, 2),
            "beginning_cash_balance": round(beginning_cash, 2),
            "ending_cash_balance": round(ending_cash, 2)
        }

if __name__ == "__main__":
    fre = FinancialReportingEngine("Acme Corp")
    rev = {"Service Revenue": 150000.0, "Product Revenue": 50000.0}
    exp = {"Cost of Goods Sold": 60000.0, "Salaries Expense": 50000.0, "Rent Expense": 12000.0}
    inc = fre.generate_income_statement(rev, exp)
    print("Income Statement Net Income:", inc["net_income"])
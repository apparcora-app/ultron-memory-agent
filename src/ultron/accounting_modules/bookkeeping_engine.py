"""
Bookkeeping & Full Accounting Cycle Engine
Handles Journal Entries, Ledger Posting, Unadjusted/Adjusted Trial Balances, and Closing Entries.
"""

class BookkeepingEngine:
    def __init__(self):
        self.accounts = {} # name: {'type': asset/liability/equity/revenue/expense, 'normal': debit/credit, 'balance': 0.0, 'ledger': []}
        self.journal_entries = []
        self.is_closed = False

    def setup_chart_of_accounts(self, coa_dict):
        # coa_dict format: {"Cash": {"type": "Asset", "normal": "Debit"}, ...}
        self.accounts = {}
        for acc, props in coa_dict.items():
            self.accounts[acc] = {
                "type": props["type"],
                "normal": props["normal"],
                "debits": 0.0,
                "credits": 0.0,
                "balance": 0.0,
                "ledger": []  # list of dicts: {"date": ..., "description": ..., "debit": ..., "credit": ..., "balance_after": ...}
            }
        self.journal_entries = []
        self.is_closed = False

    def post_journal_entry(self, description, lines, date="2026-01-01", is_adjusting=False):
        """
        lines: list of tuples -> (account_name, debit_amount, credit_amount)
        """
        # Allow closing entries even if is_closed is True (since closing entries themselves close the period)
        if self.is_closed and not description.startswith("Closing Entry:"):
            raise ValueError("The accounting period is closed. No new standard journal entries can be posted.")

        total_debits = sum(d for _, d, _ in lines)
        total_credits = sum(c for _, _, c in lines)

        if abs(total_debits - total_credits) > 1e-4:
            raise ValueError(f"Unbalanced Journal Entry! Debits: {total_debits}, Credits: {total_credits}")

        entry = {
            "date": date,
            "description": description,
            "lines": lines,
            "total": total_debits,
            "is_adjusting": is_adjusting
        }
        self.journal_entries.append(entry)

        # Post to ledger accounts
        for acc, debit, credit in lines:
            if acc not in self.accounts:
                raise KeyError(f"Account {acc} not found in Chart of Accounts.")

            acc_props = self.accounts[acc]
            acc_props["debits"] += debit
            acc_props["credits"] += credit

            # Calculate balance based on normal balance
            if acc_props["normal"] == "Debit":
                acc_props["balance"] = acc_props["debits"] - acc_props["credits"]
            else:
                acc_props["balance"] = acc_props["credits"] - acc_props["debits"]

            # Append to ledger history
            acc_props["ledger"].append({
                "date": date,
                "description": description,
                "debit": debit,
                "credit": credit,
                "balance_after": acc_props["balance"],
                "is_adjusting": is_adjusting
            })

        return True

    def get_trial_balance(self, trial_balance_type="unadjusted"):
        """
        trial_balance_type: 'unadjusted', 'adjusted', or 'post-closing'
        """
        tb = {}
        total_dr = 0.0
        total_cr = 0.0

        for acc, props in self.accounts.items():
            debits = 0.0
            credits = 0.0

            for tx in props["ledger"]:
                if trial_balance_type == "unadjusted" and tx.get("is_adjusting", False):
                    continue
                if trial_balance_type in ["unadjusted", "adjusted"] and tx["description"].startswith("Closing Entry:"):
                    continue

                debits += tx["debit"]
                credits += tx["credit"]

            if debits == 0.0 and credits == 0.0:
                continue

            # Calculate balance
            if props["normal"] == "Debit":
                bal = debits - credits
            else:
                bal = credits - debits

            if abs(bal) > 1e-4:
                if props["normal"] == "Debit":
                    tb[acc] = {"debit": bal, "credit": 0.0}
                    total_dr += bal
                else:
                    tb[acc] = {"debit": 0.0, "credit": bal}
                    total_cr += bal

        return tb, round(total_dr, 2), round(total_cr, 2)

    def post_closing_entries(self, retained_earnings_account="Retained Earnings", date="2026-12-31"):
        """
        Closes all temporary accounts (Revenue and Expense) to Retained Earnings.
        """
        if self.is_closed:
            raise ValueError("The accounting period is already closed.")

        if retained_earnings_account not in self.accounts:
            raise KeyError(f"Retained Earnings account '{retained_earnings_account}' not found in Chart of Accounts.")

        # 1. Identify revenue and expense accounts and their current adjusted balances
        closing_lines = []
        total_revenue_closed = 0.0
        total_expense_closed = 0.0

        for acc, props in self.accounts.items():
            if props["type"] in ["Revenue", "Expense"]:
                # Calculate adjusted balance
                debits = 0.0
                credits = 0.0
                for tx in props["ledger"]:
                    if not tx["description"].startswith("Closing Entry:"):
                        debits += tx["debit"]
                        credits += tx["credit"]

                if props["normal"] == "Debit":
                    bal = debits - credits
                else:
                    bal = credits - debits

                if abs(bal) > 1e-4:
                    if props["type"] == "Revenue":
                        # Revenue normally has a Credit balance. To close it, we Debit it.
                        closing_lines.append((acc, bal, 0.0))
                        total_revenue_closed += bal
                    elif props["type"] == "Expense":
                        # Expense normally has a Debit balance. To close it, we Credit it.
                        closing_lines.append((acc, 0.0, bal))
                        total_expense_closed += bal

        if not closing_lines:
            self.is_closed = True
            return []

        # Net Income = Revenue - Expense
        net_income = total_revenue_closed - total_expense_closed

        # Close to Retained Earnings
        if net_income > 0:
            closing_lines.append((retained_earnings_account, 0.0, net_income))
        elif net_income < 0:
            closing_lines.append((retained_earnings_account, abs(net_income), 0.0))

        # Post the closing entry
        self.post_journal_entry(
            description="Closing Entry: Close Revenue and Expense accounts to Retained Earnings",
            lines=closing_lines,
            date=date,
            is_adjusting=False
        )

        self.is_closed = True
        return closing_lines

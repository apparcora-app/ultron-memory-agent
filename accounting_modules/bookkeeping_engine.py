"""
Bookkeeping & Full Accounting Cycle Engine
Handles Journal Entries, Ledger Posting, Unadjusted/Adjusted Trial Balances, and Closing Entries.
"""

class BookkeepingEngine:
    def __init__(self):
        self.accounts = {} # name: {'type': asset/liability/equity/revenue/expense, 'normal': debit/credit, 'balance': 0.0}
        self.journal_entries = []

    def setup_chart_of_accounts(self, coa_dict):
        # coa_dict format: {"Cash": {"type": "Asset", "normal": "Debit"}, ...}
        for acc, props in coa_dict.items():
            self.accounts[acc] = {
                "type": props["type"],
                "normal": props["normal"],
                "debits": 0.0,
                "credits": 0.0,
                "balance": 0.0
            }

    def post_journal_entry(self, description, lines):
        """
        lines: list of tuples -> (account_name, debit_amount, credit_amount)
        """
        total_debits = sum(d for _, d, _ in lines)
        total_credits = sum(c for _, _, c in lines)

        if abs(total_debits - total_credits) > 1e-4:
            raise ValueError(f"Unbalanced Journal Entry! Debits: {total_debits}, Credits: {total_credits}")

        entry = {
            "description": description,
            "lines": lines,
            "total": total_debits
        }
        self.journal_entries.append(entry)

        # Post to ledger accounts
        for acc, debit, credit in lines:
            if acc not in self.accounts:
                raise KeyError(f"Account {acc} not found in Chart of Accounts.")
            self.accounts[acc]["debits"] += debit
            self.accounts[acc]["credits"] += credit
            
            # Calculate balance based on normal balance
            acc_props = self.accounts[acc]
            if acc_props["normal"] == "Debit":
                acc_props["balance"] = acc_props["debits"] - acc_props["credits"]
            else:
                acc_props["balance"] = acc_props["credits"] - acc_props["debits"]

        return True

    def get_trial_balance(self):
        tb = {}
        total_dr = 0.0
        total_cr = 0.0
        for acc, props in self.accounts.items():
            dr = props["debits"]
            cr = props["credits"]
            if dr > 0 or cr > 0:
                tb[acc] = {"debit": dr, "credit": cr}
                total_dr += dr
                total_cr += cr
        return tb, total_dr, total_cr

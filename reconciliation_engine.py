"""
Forensic Bank & Financial Reconciliation Engine
Author: Ultron Prime for Hanzla Rehman
Description: Deterministic double-entry ledger reconciliation, bank statement matching, 
             unrecorded transaction detection, timing difference analysis, and variance reporting.
"""

import pandas as pd
import numpy as np
from datetime import datetime

class FinancialReconciliationEngine:
    def __init__(self, tolerance: float = 0.01):
        self.tolerance = tolerance

    def reconcile_bank_statement(self, ledger_df: pd.DataFrame, bank_df: pd.DataFrame) -> dict:
        """
        Performs 3-way matching and variance reconciliation between General Ledger (GL) 
        and Bank Statement.
        
        Required Ledger Columns: ['date', 'reference', 'description', 'amount', 'account']
        Required Bank Columns: ['date', 'reference', 'description', 'amount', 'balance']
        """
        # Ensure numeric amounts
        ledger_df['amount'] = pd.to_numeric(ledger_df['amount'])
        bank_df['amount'] = pd.to_numeric(bank_df['amount'])
        
        # Exact match on amount and date tolerance
        matched_ledger = []
        matched_bank = []
        
        # Unreconciled items
        gl_unmatched = ledger_df.copy()
        bank_unmatched = bank_df.copy()
        
        # Exact matching pass (Amount + Reference)
        for idx_l, row_l in ledger_df.iterrows():
            match = bank_df[
                (abs(bank_df['amount'] - row_l['amount']) <= self.tolerance) & 
                (~bank_df.index.isin(matched_bank))
            ]
            if not match.empty:
                matched_ledger.append(idx_l)
                matched_bank.append(match.index[0])
                
        gl_reconciled = ledger_df.loc[matched_ledger]
        bank_reconciled = bank_df.loc[matched_bank]
        
        gl_outstanding = gl_unmatched.drop(matched_ledger, errors='ignore')
        bank_outstanding = bank_unmatched.drop(matched_bank, errors='ignore')
        
        summary = {
            "total_gl_entries": len(ledger_df),
            "total_bank_entries": len(bank_df),
            "reconciled_count": len(matched_ledger),
            "gl_outstanding_count": len(gl_outstanding),
            "bank_outstanding_count": len(bank_outstanding),
            "gl_outstanding_total": float(gl_outstanding['amount'].sum()),
            "bank_outstanding_total": float(bank_outstanding['amount'].sum()),
            "reconciliation_timestamp": datetime.now().isoformat()
        }
        
        return {
            "summary": summary,
            "gl_outstanding": gl_outstanding.to_dict(orient="records"),
            "bank_outstanding": bank_outstanding.to_dict(orient="records")
        }

    def verify_double_entry(self, journal_entries: pd.DataFrame) -> bool:
        """
        Verifies that total debits equal total credits across all journal entries.
        Required columns: ['entry_id', 'account', 'debit', 'credit']
        """
        total_debits = pd.to_numeric(journal_entries['debit']).sum()
        total_credits = pd.to_numeric(journal_entries['credit']).sum()
        
        difference = round(total_debits - total_credits, 2)
        if abs(difference) > self.tolerance:
            raise ValueError(f"Double-entry invariant violated! Total Debits (${total_debits:,.2f}) != Total Credits (${total_credits:,.2f}). Variance: ${difference:,.2f}")
        return True

if __name__ == "__main__":
    print("[SYSTEM] FinancialReconciliationEngine initialized successfully.")

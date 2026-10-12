"""
Comprehensive Test Suite for Bookkeeping, Payroll, Financial Reporting, and US GAAP Engines.
Verifies the full accounting cycle end-to-end.
"""

import pytest
from accounting_modules.bookkeeping_engine import BookkeepingEngine
from accounting_modules.financial_reporting import FinancialReportingEngine
from accounting_modules.payroll_engine import PayrollEngine
from accounting_modules.us_gaap_engine import USGAAPEngine

def test_full_accounting_cycle():
    # 1. Initialize Engines
    bookkeeper = BookkeepingEngine()
    reporter = FinancialReportingEngine("Titan Corp")
    payroll_eng = PayrollEngine()
    gaap_eng = USGAAPEngine()

    # 2. Setup Chart of Accounts
    coa = {
        "Cash": {"type": "Asset", "normal": "Debit"},
        "Accounts Receivable": {"type": "Asset", "normal": "Debit"},
        "Deferred Revenue": {"type": "Liability", "normal": "Credit"},
        "FICA Payable": {"type": "Liability", "normal": "Credit"},
        "Federal Withholding Payable": {"type": "Liability", "normal": "Credit"},
        "State Withholding Payable": {"type": "Liability", "normal": "Credit"},
        "FUTA Payable": {"type": "Liability", "normal": "Credit"},
        "SUTA Payable": {"type": "Liability", "normal": "Credit"},
        "Lease Liability": {"type": "Liability", "normal": "Credit"},
        "ROU Asset": {"type": "Asset", "normal": "Debit"},
        "Retained Earnings": {"type": "Equity", "normal": "Credit"},
        "Common Stock": {"type": "Equity", "normal": "Credit"},
        "Service Revenue": {"type": "Revenue", "normal": "Credit"},
        "Salaries Expense": {"type": "Expense", "normal": "Debit"},
        "Payroll Tax Expense": {"type": "Expense", "normal": "Debit"},
        "Lease Expense": {"type": "Expense", "normal": "Debit"}
    }
    bookkeeper.setup_chart_of_accounts(coa)
    assert len(bookkeeper.accounts) == 16

    # 3. Post Initial Capital Contribution
    # Debit Cash 100,000, Credit Common Stock 100,000
    bookkeeper.post_journal_entry(
        "Initial Capital Contribution",
        [
            ("Cash", 100000.0, 0.0),
            ("Common Stock", 0.0, 100000.0)
        ],
        date="2026-01-01"
    )
    assert bookkeeper.accounts["Cash"]["balance"] == 100000.0
    assert bookkeeper.accounts["Common Stock"]["balance"] == 100000.0

    # 4. Post Contract Sale with Deferred Revenue (ASC 606)
    # Debit Cash 12,000, Credit Deferred Revenue 12,000
    bookkeeper.post_journal_entry(
        "Contract Sale - 12 Month Service",
        [
            ("Cash", 12000.0, 0.0),
            ("Deferred Revenue", 0.0, 12000.0)
        ],
        date="2026-01-01"
    )
    assert bookkeeper.accounts["Deferred Revenue"]["balance"] == 12000.0

    # Generate ASC 606 Revenue Recognition Schedule
    pos = [
        {
            "id": "PO1",
            "allocated_price": 12000.0,
            "type": "over_time",
            "start_month": 1,
            "duration_months": 12
        }
    ]
    rev_schedule = gaap_eng.generate_asc_606_schedule(12000.0, pos, total_months=12)
    assert len(rev_schedule) == 12
    assert rev_schedule[0]["recognized_revenue"] == 1000.0
    assert rev_schedule[0]["deferred_revenue_balance"] == 11000.0

    # 5. Run Payroll (Payroll Engine)
    # Gross pay: 5,000, YTD: 0, Fed WH: 500, State WH: 150
    payroll_res = payroll_eng.calculate_employee_payroll(
        gross_pay=5000.0,
        ytd_earnings=0.0,
        federal_withholding=500.0,
        state_withholding=150.0
    )
    assert payroll_res["net_pay"] == 5000.0 - (310.0 + 72.5 + 500.0 + 150.0) # SS: 310, Med: 72.5
    assert payroll_res["employer_tax_burden"]["futa"] == 30.0 # 5000 * 0.006
    assert payroll_res["employer_tax_burden"]["suta"] == 135.0 # 5000 * 0.027

    # Generate and Post Payroll Journal Entry
    payroll_je = payroll_eng.generate_payroll_journal_entry(payroll_res)
    bookkeeper.post_journal_entry("Monthly Payroll Run", payroll_je, date="2026-01-31")
    
    # Verify payroll balances
    assert bookkeeper.accounts["Salaries Expense"]["balance"] == 5000.0
    assert bookkeeper.accounts["Payroll Tax Expense"]["balance"] == payroll_res["employer_tax_burden"]["total_employer_tax"]

    # 6. Lease Recognition (ASC 842)
    # Operating Lease: 12 months, 5% annual discount rate, $1,000 monthly payment
    lease_schedule = gaap_eng.generate_asc_842_schedule(
        lease_term_months=12,
        annual_discount_rate=0.05,
        monthly_payment=1000.0,
        lease_type="Operating"
    )
    initial_pv = lease_schedule[0]["lease_liability_balance"]
    assert initial_pv > 11000.0 # PV of 12 payments of 1000 at 5% is ~11,681.22

    # Post Initial Lease Recognition
    # Debit ROU Asset, Credit Lease Liability
    bookkeeper.post_journal_entry(
        "Initial Lease Recognition (ASC 842)",
        [
            ("ROU Asset", initial_pv, 0.0),
            ("Lease Liability", 0.0, initial_pv)
        ],
        date="2026-01-01"
    )
    assert bookkeeper.accounts["ROU Asset"]["balance"] == initial_pv
    assert bookkeeper.accounts["Lease Liability"]["balance"] == initial_pv

    # 7. Post Month-End Adjusting Entries (January 31)
    # A. Recognize 1 month of revenue under ASC 606
    # Debit Deferred Revenue 1,000, Credit Service Revenue 1,000
    bookkeeper.post_journal_entry(
        "Adjusting Entry: ASC 606 Revenue Recognition Month 1",
        [
            ("Deferred Revenue", 1000.0, 0.0),
            ("Service Revenue", 0.0, 1000.0)
        ],
        date="2026-01-31",
        is_adjusting=True
    )

    # B. Record 1 month of lease expense under ASC 842
    # Operating Lease: Debit Lease Expense 1,000, Credit Cash 1,000 (payment)
    # Adjusting portion: Debit Lease Liability (principal reduction), Credit ROU Asset (amortization)
    jan_lease = lease_schedule[1]
    bookkeeper.post_journal_entry(
        "Lease Payment - Month 1",
        [
            ("Lease Expense", 1000.0, 0.0),
            ("Cash", 0.0, 1000.0)
        ],
        date="2026-01-31"
    )
    bookkeeper.post_journal_entry(
        "Adjusting Entry: ASC 842 Lease Amortization Month 1",
        [
            ("Lease Liability", jan_lease["amortization_expense"], 0.0),
            ("ROU Asset", 0.0, jan_lease["amortization_expense"])
        ],
        date="2026-01-31",
        is_adjusting=True
    )

    # Verify balances after adjusting entries
    assert bookkeeper.accounts["Deferred Revenue"]["balance"] == 11000.0
    assert bookkeeper.accounts["Service Revenue"]["balance"] == 1000.0
    assert round(bookkeeper.accounts["Lease Liability"]["balance"], 2) == jan_lease["lease_liability_balance"]
    assert round(bookkeeper.accounts["ROU Asset"]["balance"], 2) == jan_lease["rou_asset_balance"]

    # 8. Generate Trial Balances
    unadj_tb, unadj_dr, unadj_cr = bookkeeper.get_trial_balance("unadjusted")
    assert unadj_dr == unadj_cr
    # Unadjusted should not include adjusting entries (so Service Revenue should not be in it)
    assert "Service Revenue" not in unadj_tb

    adj_tb, adj_dr, adj_cr = bookkeeper.get_trial_balance("adjusted")
    assert adj_dr == adj_cr
    assert "Service Revenue" in adj_tb

    # 9. Generate Financial Statements
    inc_stmt = reporter.generate_income_statement_from_ledger(bookkeeper)
    assert inc_stmt["net_income"] == 1000.0 - (5000.0 + payroll_res["employer_tax_burden"]["total_employer_tax"] + 1000.0)
    
    bal_sheet = reporter.generate_balance_sheet_from_ledger(bookkeeper)
    assert bal_sheet["is_balanced"] is True

    # 10. Post Closing Entries
    closing_lines = bookkeeper.post_closing_entries(retained_earnings_account="Retained Earnings", date="2026-01-31")
    assert len(closing_lines) > 0
    assert bookkeeper.is_closed is True

    # Verify temporary accounts are closed to 0
    post_closing_tb, pc_dr, pc_cr = bookkeeper.get_trial_balance("post-closing")
    assert pc_dr == pc_cr
    assert "Service Revenue" not in post_closing_tb
    assert "Salaries Expense" not in post_closing_tb
    assert "Payroll Tax Expense" not in post_closing_tb
    assert "Lease Expense" not in post_closing_tb
    
    # Retained Earnings should now have the Net Income/Loss balance
    assert round(bookkeeper.accounts["Retained Earnings"]["balance"], 2) == inc_stmt["net_income"]


def test_asc_350_goodwill_impairment():
    gaap_eng = USGAAPEngine()
    
    # Case A: No impairment
    res_no = gaap_eng.evaluate_asc_350_impairment(
        reporting_unit_name="North America Retail",
        carrying_value=500000.0,
        fair_value=550000.0,
        allocated_goodwill=100000.0
    )
    assert res_no["impairment_required"] is False
    assert res_no["impairment_loss"] == 0.0
    assert res_no["new_goodwill_value"] == 100000.0

    # Case B: Impairment capped at goodwill
    res_cap = gaap_eng.evaluate_asc_350_impairment(
        reporting_unit_name="Europe Retail",
        carrying_value=500000.0,
        fair_value=350000.0,
        allocated_goodwill=100000.0
    )
    assert res_cap["impairment_required"] is True
    assert res_cap["impairment_loss"] == 100000.0 # capped at allocated goodwill
    assert res_cap["new_goodwill_value"] == 0.0

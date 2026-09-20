"""
Payroll Calculation & Tax-Remittance Engine
Calculates Gross-to-Net, FICA (Social Security & Medicare), Federal/State Withholding, and Employer Taxes.
Generates compliant journal entries for posting to the Bookkeeping Engine.
"""

class PayrollEngine:
    def __init__(self):
        # 2026 standard tax parameters
        self.ss_tax_rate = 0.062
        self.ss_wage_base = 176100.0  # Estimated 2026 wage base
        self.medicare_rate = 0.0145
        self.medicare_additional_rate = 0.009
        self.medicare_additional_threshold = 200000.0
        self.futa_rate = 0.006
        self.futa_wage_base = 7000.0
        self.suta_rate = 0.027  # Standard state unemployment tax rate
        self.suta_wage_base = 10000.0  # Standard state wage base

    def calculate_employee_payroll(self, gross_pay, ytd_earnings=0.0, federal_withholding=0.0, state_withholding=0.0):
        # Social Security
        remaining_ss_base = max(0.0, self.ss_wage_base - ytd_earnings)
        taxable_ss = min(gross_pay, remaining_ss_base)
        ss_tax = taxable_ss * self.ss_tax_rate

        # Medicare
        medicare_tax = gross_pay * self.medicare_rate
        if ytd_earnings + gross_pay > self.medicare_additional_threshold:
            excess_ytd = max(0.0, ytd_earnings - self.medicare_additional_threshold)
            taxable_additional = (ytd_earnings + gross_pay - self.medicare_additional_threshold) - excess_ytd
            medicare_tax += taxable_additional * self.medicare_additional_rate

        total_employee_taxes = ss_tax + medicare_tax + federal_withholding + state_withholding
        net_pay = gross_pay - total_employee_taxes

        # Employer Taxes
        employer_ss = ss_tax
        employer_medicare = gross_pay * self.medicare_rate
        
        remaining_futa_base = max(0.0, self.futa_wage_base - ytd_earnings)
        taxable_futa = min(gross_pay, remaining_futa_base)
        employer_futa = taxable_futa * self.futa_rate

        remaining_suta_base = max(0.0, self.suta_wage_base - ytd_earnings)
        taxable_suta = min(gross_pay, remaining_suta_base)
        employer_suta = taxable_suta * self.suta_rate

        total_employer_tax = employer_ss + employer_medicare + employer_futa + employer_suta

        return {
            "gross_pay": round(gross_pay, 2),
            "social_security": round(ss_tax, 2),
            "medicare": round(medicare_tax, 2),
            "federal_withholding": round(federal_withholding, 2),
            "state_withholding": round(state_withholding, 2),
            "total_deductions": round(total_employee_taxes, 2),
            "net_pay": round(net_pay, 2),
            "employer_tax_burden": {
                "social_security": round(employer_ss, 2),
                "medicare": round(employer_medicare, 2),
                "futa": round(employer_futa, 2),
                "suta": round(employer_suta, 2),
                "total_employer_tax": round(total_employer_tax, 2)
            }
        }

    def generate_payroll_journal_entry(self, payroll_results, salaries_expense_acc="Salaries Expense", payroll_tax_expense_acc="Payroll Tax Expense", cash_acc="Cash"):
        """
        Generates journal entry lines for a payroll run.
        """
        gross_pay = payroll_results["gross_pay"]
        net_pay = payroll_results["net_pay"]
        emp_ss = payroll_results["social_security"]
        emp_med = payroll_results["medicare"]
        fed_wh = payroll_results["federal_withholding"]
        state_wh = payroll_results["state_withholding"]
        
        er_ss = payroll_results["employer_tax_burden"]["social_security"]
        er_med = payroll_results["employer_tax_burden"]["medicare"]
        er_futa = payroll_results["employer_tax_burden"]["futa"]
        er_suta = payroll_results["employer_tax_burden"]["suta"]
        er_total = payroll_results["employer_tax_burden"]["total_employer_tax"]

        # Debits
        lines = [
            (salaries_expense_acc, gross_pay, 0.0),
            (payroll_tax_expense_acc, er_total, 0.0)
        ]

        # Credits
        # FICA Payable includes both employee and employer SS & Medicare
        fica_payable = round(emp_ss + emp_med + er_ss + er_med, 2)
        if fica_payable > 0:
            lines.append(("FICA Payable", 0.0, fica_payable))
            
        if fed_wh > 0:
            lines.append(("Federal Withholding Payable", 0.0, fed_wh))
            
        if state_wh > 0:
            lines.append(("State Withholding Payable", 0.0, state_wh))
            
        if er_futa > 0:
            lines.append(("FUTA Payable", 0.0, er_futa))
            
        if er_suta > 0:
            lines.append(("SUTA Payable", 0.0, er_suta))
            
        if net_pay > 0:
            lines.append((cash_acc, 0.0, net_pay))

        # Double check balance due to rounding
        total_debits = round(sum(d for _, d, _ in lines), 2)
        total_credits = round(sum(c for _, _, c in lines), 2)
        diff = round(total_debits - total_credits, 2)
        
        if abs(diff) > 0.0:
            # Adjust the cash line or salaries expense line slightly to balance rounding errors
            for i, (acc, d, c) in enumerate(lines):
                if acc == cash_acc:
                    lines[i] = (acc, d, round(c + diff, 2))
                    break

        return lines
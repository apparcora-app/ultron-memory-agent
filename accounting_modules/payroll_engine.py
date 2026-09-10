"""
Payroll Calculation & Tax-Remittance Engine
Calculates Gross-to-Net, FICA (Social Security & Medicare), Federal/State Withholding, and Employer Taxes.
"""

class PayrollEngine:
    def __init__(self):
        # 2026/2025 standard tax parameters
        self.ss_tax_rate = 0.062
        self.ss_wage_base = 176100.0  # Estimated 2026 wage base
        self.medicare_rate = 0.0145
        self.medicare_additional_rate = 0.009
        self.medicare_additional_threshold = 200000.0
        self.futa_rate = 0.006
        self.futa_wage_base = 7000.0

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
                "total_employer_tax": round(employer_ss + employer_medicare + employer_futa, 2)
            }
        }

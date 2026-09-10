"""
Individual Tax Computation Module (Form 1040 & Schedule C / SE)
Author: ULTRON PRIME for Hanzla Rehman
"""

def calculate_individual_tax(w2_income=0, self_employment_income=0, filing_status="single", year=2025):
    # 2025 Tax Brackets & Standard Deductions (approximate / IRS baseline)
    std_deductions = {
        "single": 15000,
        "married_joint": 30000,
        "head_of_household": 22500
    }
    
    # Simple self-employment tax calculation (Schedule SE: 15.3% on 92.35% of net earnings)
    se_tax = 0
    net_se_earnings = 0
    if self_employment_income > 0:
        net_se_earnings = self_employment_income * 0.9235
        # Social Security (12.4% up to wage base e.g. $176,100) + Medicare (2.9%)
        ss_wage_base = 176100
        ss_tax = min(net_se_earnings, ss_wage_base) * 0.124
        medicare_tax = net_se_earnings * 0.029
        se_tax = ss_tax + medicare_tax
        # Half of SE tax is an above-the-line deduction
        se_deduction = se_tax / 2
    else:
        se_deduction = 0

    total_earned = w2_income + self_employment_income
    std_ded = std_deductions.get(filing_status, 15000)
    
    # Adjusted Gross Income (AGI) approximation
    agi = total_earned - se_deduction
    taxable_income = max(0, agi - std_ded)
    
    # Simplified progressive tax brackets (Single 2025 model)
    brackets = [
        (11600, 0.10),
        (47150, 0.12),
        (100525, 0.22),
        (191950, 0.24),
        (243725, 0.32),
        (609350, 0.35),
        (float('inf'), 0.37)
    ]
    
    tax = 0
    prev_limit = 0
    for limit, rate in brackets:
        if taxable_income > limit:
            tax += (limit - prev_limit) * rate
            prev_limit = limit
        else:
            tax += (taxable_income - prev_limit) * rate
            break
            
    total_tax_liability = tax + se_tax
    
    return {
        "filing_status": filing_status,
        "w2_income": w2_income,
        "self_employment_income": self_employment_income,
        "agi": agi,
        "standard_deduction": std_ded,
        "taxable_income": taxable_income,
        "income_tax": round(tax, 2),
        "self_employment_tax": round(se_tax, 2),
        "total_tax_liability": round(total_tax_liability, 2)
    }

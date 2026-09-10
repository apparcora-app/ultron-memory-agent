"""
Corporate Tax Computation Module (Form 1120 C-Corp & Form 1120-S Passthrough)
Author: ULTRON PRIME for Hanzla Rehman
"""

def calculate_corporate_tax(entity_type="C-Corp", gross_receipts=0, total_deductions=0, w2_officer_salary=0):
    net_income = gross_receipts - total_deductions
    
    if entity_type.upper() == "C-CORP":
        # US Federal C-Corp flat tax rate is 21%
        taxable_income = max(0, net_income)
        federal_tax = taxable_income * 0.21
        return {
            "entity_type": "C-Corp",
            "gross_receipts": gross_receipts,
            "total_deductions": total_deductions,
            "net_income": net_income,
            "taxable_income": taxable_income,
            "federal_corporate_tax_21_pct": round(federal_tax, 2),
            "effective_tax_rate": round((federal_tax / gross_receipts) * 100, 2) if gross_receipts > 0 else 0.0
        }
        
    elif entity_type.upper() in ["S-CORP", "S_CORP"]:
        # S-Corp is a pass-through entity. Net income passes to shareholders via Schedule K-1.
        # Officer must take reasonable compensation (W-2 salary subject to FICA).
        return {
            "entity_type": "S-Corp (Pass-Through)",
            "gross_receipts": gross_receipts,
            "total_deductions": total_deductions,
            "officer_w2_salary": w2_officer_salary,
            "pass_through_ordinary_income": max(0, net_income - w2_officer_salary),
            "federal_corporate_level_tax": 0.0,
            "note": "S-Corp does not pay federal income tax at entity level; income passes through to Form 1040 Schedule E."
        }
    else:
        raise ValueError(f"Unknown entity type: {entity_type}")

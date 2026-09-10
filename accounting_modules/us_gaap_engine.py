"""
US GAAP & FASB Accounting Standards Codification (ASC) Compliance Engine
Authoritative guidance rules for revenue recognition (ASC 606), leases (ASC 842), 
goodwill/intangibles (ASC 350), and financial statement presentation.
"""

class USGAAPEngine:
    def __init__(self):
        self.standards = {
            "ASC 606": {
                "title": "Revenue from Contracts with Customers",
                "core_principle": "Recognize revenue to depict the transfer of promised goods or services to customers in an amount that reflects the consideration to which the entity expects to be entitled.",
                "five_steps": [
                    "1. Identify the contract(s) with a customer.",
                    "2. Identify the performance obligations in the contract.",
                    "3. Determine the transaction price.",
                    "4. Allocate the transaction price to the performance obligations.",
                    "5. Recognize revenue when (or as) the entity satisfies a performance obligation."
                ]
            },
            "ASC 842": {
                "title": "Leases",
                "core_principle": "Lessees recognize lease assets and lease liabilities on the balance sheet for all leases with lease terms greater than 12 months.",
                "classification": "Classifies leases as either Operating or Finance based on transfer of control, ownership, purchase option, term (>75% useful life), and present value (>90% fair value)."
            },
            "ASC 350": {
                "title": "Intangibles—Goodwill and Other",
                "core_principle": "Goodwill is not amortized; it is tested for impairment at least annually at the reporting unit level.",
                "impairment_test": "Qualitative assessment or quantitative two-step test comparing fair value of reporting unit to its carrying amount."
            },
            "ASC 830": {
                "title": "Foreign Currency Matters",
                "core_principle": "Translation of financial statements of foreign entities using current rate method (balance sheet at closing rate, income statement at weighted average rate)."
            }
        }

    def evaluate_asc_606(self, contract_id, steps_completed):
        """Validates compliance against the 5-step model of ASC 606."""
        completed_count = len([s for s in steps_completed if s])
        compliant = completed_count == 5
        return {
            "standard": "ASC 606",
            "contract_id": contract_id,
            "steps_completed_count": completed_count,
            "fully_compliant": compliant,
            "details": self.standards["ASC 606"]["five_steps"]
        }

    def evaluate_asc_842_lease(self, lease_term_months, pv_lease_payments, fair_value_asset):
        """Determines whether a lease is Operating or Finance under ASC 842."""
        is_finance = (lease_term_months > (0.75 * 12 * 10)) or (pv_lease_payments >= (0.90 * fair_value_asset))
        lease_type = "Finance Lease" if is_finance else "Operating Lease"
        return {
            "standard": "ASC 842",
            "lease_type": lease_type,
            "recognized_on_balance_sheet": True, # Required for both under ASC 842
            "right_of_use_asset": pv_lease_payments
        }

if __name__ == "__main__":
    engine = USGAAPEngine()
    print("US GAAP Compliance Engine Initialized Successfully.")

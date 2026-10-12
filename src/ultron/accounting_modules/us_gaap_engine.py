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

    def generate_asc_606_schedule(self, contract_price, performance_obligations, total_months=12):
        """
        Generates a month-by-month revenue recognition schedule under ASC 606.
        performance_obligations: list of dicts:
            {
                "id": "PO1",
                "allocated_price": 12000.0,
                "type": "over_time" | "point_in_time",
                "start_month": 1,
                "duration_months": 12  # only for over_time
            }
        """
        schedule = []
        deferred_revenue = contract_price
        cumulative_recognized = 0.0

        # Verify allocation
        allocated_total = sum(po["allocated_price"] for po in performance_obligations)
        if abs(allocated_total - contract_price) > 1e-2:
            raise ValueError(f"Sum of allocated prices ({allocated_total}) does not match contract price ({contract_price})")

        for month in range(1, total_months + 1):
            recognized_this_month = 0.0
            po_breakdown = {}

            for po in performance_obligations:
                po_id = po["id"]
                price = po["allocated_price"]
                po_type = po["type"]
                start = po["start_month"]

                if po_type == "point_in_time":
                    if month == start:
                        recognized_this_month += price
                        po_breakdown[po_id] = price
                    else:
                        po_breakdown[po_id] = 0.0
                elif po_type == "over_time":
                    duration = po["duration_months"]
                    end = start + duration - 1
                    if start <= month <= end:
                        monthly_rev = price / duration
                        recognized_this_month += monthly_rev
                        po_breakdown[po_id] = round(monthly_rev, 2)
                    else:
                        po_breakdown[po_id] = 0.0

            recognized_this_month = round(recognized_this_month, 2)
            deferred_revenue = round(deferred_revenue - recognized_this_month, 2)
            cumulative_recognized = round(cumulative_recognized + recognized_this_month, 2)

            schedule.append({
                "month": month,
                "recognized_revenue": recognized_this_month,
                "deferred_revenue_balance": max(0.0, deferred_revenue),
                "cumulative_recognized_revenue": cumulative_recognized,
                "breakdown": po_breakdown
            })

        return schedule

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

    def generate_asc_842_schedule(self, lease_term_months, annual_discount_rate, monthly_payment, lease_type="Operating"):
        """
        Generates a month-by-month lease amortization schedule under ASC 842.
        """
        r = annual_discount_rate / 12.0

        # Calculate Present Value of Lease Payments (Ordinary Annuity)
        if r > 0:
            pv = monthly_payment * ((1 - (1 + r) ** -lease_term_months) / r)
        else:
            pv = monthly_payment * lease_term_months

        pv = round(pv, 2)

        schedule = []
        lease_liability = pv
        rou_asset = pv

        # Month 0 (Initial Recognition)
        schedule.append({
            "month": 0,
            "payment": 0.0,
            "interest_expense": 0.0,
            "amortization_expense": 0.0,
            "total_lease_expense": 0.0,
            "lease_liability_balance": lease_liability,
            "rou_asset_balance": rou_asset
        })

        straight_line_lease_cost = round(monthly_payment, 2) if lease_type == "Operating" else 0.0

        for month in range(1, lease_term_months + 1):
            interest = round(lease_liability * r, 2)
            principal_reduction = round(monthly_payment - interest, 2)
            lease_liability = round(lease_liability - principal_reduction, 2)

            if lease_type == "Finance":
                # Finance Lease: Interest + Straight-line Amortization of ROU Asset
                amortization = round(pv / lease_term_months, 2)
                rou_asset = round(rou_asset - amortization, 2)
                total_expense = round(interest + amortization, 2)
                interest_expense = interest
                amortization_expense = amortization
            else:
                # Operating Lease: Single straight-line lease cost, ROU asset reduction is plug
                total_expense = straight_line_lease_cost
                amortization = round(straight_line_lease_cost - interest, 2)
                rou_asset = round(rou_asset - amortization, 2)
                interest_expense = 0.0  # Presented as single lease cost, not interest expense
                amortization_expense = amortization

            schedule.append({
                "month": month,
                "payment": round(monthly_payment, 2),
                "interest_portion": interest,
                "interest_expense": interest_expense,
                "amortization_expense": amortization_expense,
                "total_lease_expense": total_expense,
                "lease_liability_balance": max(0.0, lease_liability),
                "rou_asset_balance": max(0.0, rou_asset)
            })

        return schedule

    def evaluate_asc_350_impairment(self, reporting_unit_name, carrying_value, fair_value, allocated_goodwill):
        """
        Performs quantitative goodwill impairment test under ASC 350.
        """
        impairment_required = fair_value < carrying_value
        impairment_loss = 0.0

        if impairment_required:
            # Impairment loss is the difference, capped at the allocated goodwill amount
            difference = carrying_value - fair_value
            impairment_loss = min(difference, allocated_goodwill)

        impairment_loss = round(impairment_loss, 2)
        new_goodwill_value = round(allocated_goodwill - impairment_loss, 2)

        return {
            "standard": "ASC 350",
            "reporting_unit": reporting_unit_name,
            "impairment_required": impairment_required,
            "carrying_value": round(carrying_value, 2),
            "fair_value": round(fair_value, 2),
            "allocated_goodwill": round(allocated_goodwill, 2),
            "impairment_loss": impairment_loss,
            "new_goodwill_value": new_goodwill_value
        }

if __name__ == "__main__":
    engine = USGAAPEngine()
    print("US GAAP Compliance Engine Initialized Successfully.")

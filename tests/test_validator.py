import csv
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from validator import validate_row  # noqa: E402

GOOD = {
    "request_id": "r1", "amount_safe_to_pay": "1000", "affordability_status": "affordable_now",
    "recommended_payment_method": "full_payment", "payment_plan": "2026-01-01:1000",
    "earliest_date_for_full_payment": "2026-01-01", "spending_changes_needed": "none",
    "decision_explanation": "Pay 1000 today. This leaves at least 500 available.",
}
REQUEST = {"request_id": "r1", "request_date": "2026-01-01",
           "desired_completion_date": "2026-02-01", "requested_amount": "1000",
           "allows_partial_payment": "false"}
PROFILE = {"payment_methods_user_will_consider": "full_payment|partial_payment|installments",
           "expense_categories_user_is_willing_to_stop": "streaming",
           "expense_categories_user_is_willing_to_reduce": "dining"}
RECURRING = {
    "event_1": {"flexibility": "stoppable", "category": "streaming",
                "minimum_allowed_amount": ""},
    "event_2": {"flexibility": "reducible", "category": "dining",
                "minimum_allowed_amount": "50"},
}


def base(**over):
    row = dict(GOOD)
    row.update(over)
    return row


class TestValidator(unittest.TestCase):
    def valid(self, row, request=REQUEST, profile=PROFILE, options=None, index=RECURRING):
        return validate_row(row, request, profile, options or [], index)

    def test_gold_style_row_passes(self):
        self.assertEqual(self.valid(base()), [])

    def test_out_of_bounds_asp(self):
        self.assertTrue(any("outside" in x for x in self.valid(base(amount_safe_to_pay="2000"))))
        self.assertTrue(any("outside" in x for x in self.valid(base(amount_safe_to_pay="-5"))))

    def test_bad_enum(self):
        self.assertTrue(any("invalid affordability_status" in x
                            for x in self.valid(base(affordability_status="maybe"))))

    def test_affordable_now_requires_earliest_eq_request_date(self):
        self.assertTrue(any("earliest" in x for x in
                            self.valid(base(earliest_date_for_full_payment="2026-01-02"))))

    def test_affordable_now_requires_full_payment_method(self):
        self.assertTrue(any("full_payment" in x for x in
                            self.valid(base(recommended_payment_method="wait"))))

    def test_missing_column(self):
        row = base()
        del row["payment_plan"]
        self.assertTrue(any("missing column" in x for x in self.valid(row)))

    def test_malformed_plan(self):
        self.assertTrue(any("malformed" in x for x in
                            self.valid(base(payment_plan="2026-01-01:abc"))))

    def test_wait_requires_full_payment_considered(self):
        p = dict(PROFILE, payment_methods_user_will_consider="installments")
        row = base(recommended_payment_method="wait", affordability_status="affordable_later",
                   payment_plan="2026-03-01:1000", earliest_date_for_full_payment="2026-03-01")
        self.assertTrue(any("full_payment" in x for x in self.valid(row, profile=p)))

    def test_wait_plan_shape(self):
        row = base(recommended_payment_method="wait", affordability_status="affordable_later",
                   payment_plan="2026-03-01:500", earliest_date_for_full_payment="2026-03-01")
        self.assertTrue(any("wait must be" in x for x in self.valid(row)))

    def test_partial_rules(self):
        row = base(amount_safe_to_pay="400", affordability_status="affordable_with_plan",
                   recommended_payment_method="partial_payment",
                   payment_plan="2026-01-01:400|2026-02-01:600",
                   earliest_date_for_full_payment="2026-02-01")
        req = dict(REQUEST, allows_partial_payment="true", requested_amount="1000")
        self.assertEqual(self.valid(row, request=req), [])
        # second payment on wrong date
        bad = base(amount_safe_to_pay="400", affordability_status="affordable_with_plan",
                   recommended_payment_method="partial_payment",
                   payment_plan="2026-01-01:400|2026-02-03:600",
                   earliest_date_for_full_payment="2026-02-01")
        self.assertTrue(any("second partial" in x for x in self.valid(bad, request=req)))

    def test_installments_must_match_option(self):
        opts = [{"payment_option_id": "po1", "payment_method": "installments",
                 "payment_amount_f": 500.0, "n_payments_i": 2,
                 "first_date_d": date(2026, 1, 1), "freq_i": 30}]
        row = base(amount_safe_to_pay="0", affordability_status="affordable_with_plan",
                   recommended_payment_method="installments",
                   payment_plan="2026-01-01:500|2026-01-31:500",
                   earliest_date_for_full_payment="2026-02-01")
        self.assertEqual(self.valid(row, options=opts), [])
        bad = dict(row, payment_plan="2026-01-01:500|2026-01-30:500")
        self.assertTrue(any("does not exactly match" in x for x in self.valid(bad, options=opts)))

    def test_spending_changes_rules(self):
        row = base(spending_changes_needed="stop:event_1", earliest_date_for_full_payment="")
        row["affordability_status"] = "not_affordable"
        row["recommended_payment_method"] = "not_recommended"
        row["payment_plan"] = "none"
        self.assertEqual(self.valid(row), [])
        # reduce below floor
        self.assertTrue(any("minimum_allowed_amount" in x for x in
                            self.valid(base(spending_changes_needed="reduce_to:event_2:10"))))
        # stop+reduce same event
        self.assertTrue(any("same event" in x for x in
                            self.valid(base(spending_changes_needed="stop:event_2|reduce_to:event_2:60"))))
        # category not willing
        self.assertTrue(any("not willing to stop" in x for x in
                            self.valid(base(spending_changes_needed="stop:event_2"))))

    def test_empty_earliest_rules(self):
        # affordable_now must carry earliest == request_date (covered elsewhere);
        # affordable_with_plan may legally have empty earliest when the lump sum
        # is never forecast-safe (spec sentence), e.g. installments completing it
        row = base(earliest_date_for_full_payment="",
                   affordability_status="affordable_with_plan",
                   recommended_payment_method="installments",
                   payment_plan="2026-01-01:500|2026-01-31:500")
        opts = [{"payment_option_id": "po1", "payment_method": "installments",
                 "payment_amount_f": 500.0, "n_payments_i": 2,
                 "first_date_d": date(2026, 1, 1), "freq_i": 30}]
        self.assertEqual(self.valid(row, options=opts), [])
        # affordable_later still requires earliest (wait pays on it)
        self.assertTrue(any("affordable_later requires earliest" in x
                            for x in self.valid(base(earliest_date_for_full_payment="",
                                                     recommended_payment_method="wait",
                                                     affordability_status="affordable_later",
                                                     payment_plan="none"))))


if __name__ == "__main__":
    unittest.main()

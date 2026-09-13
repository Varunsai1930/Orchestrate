import csv
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "code" / "evaluation"))

from evaluation.score import compare_row, load_rows  # noqa: E402
from validator import validate_row  # noqa: E402

SAMPLES = ROOT / "dataset" / "sample_requests.csv"
EVENTS = ROOT / "dataset" / "financial_events.csv"
PROFILES = ROOT / "dataset" / "financial_profiles.csv"
OPTIONS = ROOT / "dataset" / "request_payment_options.csv"


def load_all(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


class TestSelfScore(unittest.TestCase):
    """Scoring the gold against itself must give 100% on every field."""

    def test_self_score_perfect(self):
        rows = load_rows(SAMPLES)
        for rid, gold in rows.items():
            res = compare_row(gold, gold)
            for field, ok in res.items():
                self.assertTrue(ok, f"{rid}.{field} should match itself")


class TestGoldPassesValidator(unittest.TestCase):
    """All 25 solved samples must satisfy the validator — gold is truth."""

    def test_all_gold_rows_valid(self):
        samples = load_all(SAMPLES)
        profiles = {r["user_id"]: r for r in load_all(PROFILES)}
        from state import load_corpus
        options = load_corpus().options_by_request
        recurring = {}
        for r in load_all(EVENTS):
            if r["flexibility"] and r["flexibility"] != "fixed":
                recurring[r["event_id"]] = {
                    "flexibility": r["flexibility"], "category": r["category"],
                    "minimum_allowed_amount": r["minimum_allowed_amount"]}
        invalid = []
        for row in samples:
            problems = validate_row(row, row, profiles[row["user_id"]],
                                    options.get(row["request_id"], []), recurring)
            if problems:
                invalid.append((row["request_id"], problems))
        self.assertEqual(invalid, [])


class TestScorePerturbation(unittest.TestCase):
    """Perturbing one field at a time must flip exactly that field to fail."""

    def setUp(self):
        self.rows = load_rows(SAMPLES)
        self.rid = "request_01"
        self.gold = self.rows[self.rid]

    def perturb(self, field, value):
        pred = dict(self.gold)
        pred[field] = value
        return compare_row(pred, self.gold)

    def test_amount_perturbation_fails(self):
        self.assertFalse(self.perturb("amount_safe_to_pay", "1")["amount_safe_to_pay"])

    def test_status_perturbation_fails(self):
        self.assertFalse(self.perturb("affordability_status", "not_affordable")["affordability_status"])

    def test_plan_perturbation_fails(self):
        self.assertFalse(self.perturb("payment_plan", "none")["payment_plan"])

    def test_identical_passes_everything(self):
        res = compare_row(self.gold, self.gold)
        self.assertTrue(all(res.values()))


if __name__ == "__main__":
    unittest.main()

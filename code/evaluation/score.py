"""Field-level scoring against the 25 solved samples (CONTRACT.md §7).

Usage:
    python3 code/evaluation/score.py --pred <output.csv> --gold dataset/sample_requests.csv
"""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import AMOUNT_TOLERANCE  # noqa: E402
from state import parse_amount as _num  # noqa: E402
from validator import _parse_changes, _parse_plan  # noqa: E402

FIELDS = ["amount_safe_to_pay", "affordability_status", "recommended_payment_method",
          "payment_plan", "earliest_date_for_full_payment",
          "spending_changes_needed", "decision_explanation"]


def _close(a, b):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= max(1.0, AMOUNT_TOLERANCE * max(abs(a), abs(b)))


def compare_row(pred, gold):
    """Return {field: bool} for one request."""
    result = {}
    result["amount_safe_to_pay"] = _close(_num(pred["amount_safe_to_pay"]),
                                          _num(gold["amount_safe_to_pay"]))
    result["affordability_status"] = (pred["affordability_status"] or "").strip() == \
                                     (gold["affordability_status"] or "").strip()
    result["recommended_payment_method"] = (pred["recommended_payment_method"] or "").strip() == \
                                           (gold["recommended_payment_method"] or "").strip()

    pp, gp = _parse_plan(pred["payment_plan"]), _parse_plan(gold["payment_plan"])
    ok = False
    if pp is not None and gp is not None and len(pp) == len(gp):
        pp_by_date = {d: a for d, a in pp}
        ok = all(d in pp_by_date and _close(pp_by_date[d], a) for d, a in gp)
    result["payment_plan"] = ok

    pe = (pred["earliest_date_for_full_payment"] or "").strip()
    ge = (gold["earliest_date_for_full_payment"] or "").strip()
    result["earliest_date_for_full_payment"] = pe == ge

    pc, gc = _parse_changes(pred["spending_changes_needed"]), _parse_changes(gold["spending_changes_needed"])
    ok = len(pc) == len(gc)
    if ok:
        gold_stops = {c[1] for c in gc if c[0] == "stop"}
        pred_stops = {c[1] for c in pc if c[0] == "stop"}
        gold_reduces = {c[1]: c[2] for c in gc if c[0] == "reduce"}
        pred_reduces = {c[1]: c[2] for c in pc if c[0] == "reduce"}
        ok = gold_stops == pred_stops and set(gold_reduces) == set(pred_reduces) \
            and all(_close(pred_reduces[e], a) for e, a in gold_reduces.items())
    result["spending_changes_needed"] = ok

    result["decision_explanation"] = bool((pred["decision_explanation"] or "").strip())
    return result


def load_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return {r["request_id"]: r for r in csv.DictReader(f)}


def main():
    ap = argparse.ArgumentParser(description="Score predictions vs solved samples")
    ap.add_argument("--pred", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--json", default=None, help="write JSON report here")
    args = ap.parse_args()

    pred = load_rows(args.pred)
    gold = load_rows(args.gold)

    per_field = {f: [0, 0] for f in FIELDS}
    row_results = {}
    for rid, grow in gold.items():
        prow = pred.get(rid)
        if prow is None:
            row_results[rid] = {f: False for f in FIELDS}
        else:
            row_results[rid] = compare_row(prow, grow)
        for f in FIELDS:
            per_field[f][1] += 1
            per_field[f][0] += row_results[rid][f]

    total_correct = sum(c for c, _ in per_field.values())
    total = sum(n for _, n in per_field.values())

    print("=" * 64)
    print(f" SCORE: {args.pred} vs {args.gold}")
    print("=" * 64)
    for f in FIELDS:
        c, n = per_field[f]
        print(f"  {f:34} {c:>3}/{n:<3} {c / n:.1%}" if n else f"  {f:34} n/a")
    print(f"  {'TOTAL':34} {total_correct:>3}/{total:<3} {total_correct / total:.1%}")

    print("\nper-row failures:")
    for rid, res in row_results.items():
        failed = [f for f in FIELDS if not res[f]]
        if failed:
            print(f"  {rid}: {', '.join(failed)}")

    if args.json:
        report = {
            "pred": args.pred, "gold": args.gold,
            "per_field": {f: {"correct": c, "total": n, "acc": round(c / n, 4) if n else None}
                          for f, (c, n) in per_field.items()},
            "total": {"correct": total_correct, "total": total,
                      "score": round(total_correct / total, 4) if total else None},
            "rows": row_results,
        }
        Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nJSON report: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

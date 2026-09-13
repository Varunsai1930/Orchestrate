"""Failure-cluster analysis for sample-based eval (CONTRACT.md §7).

Usage:
    python3 code/evaluation/analyze.py --pred <output.csv> --gold dataset/sample_requests.csv
"""
import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.score import FIELDS, compare_row, load_rows  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Analyze eval failures")
    ap.add_argument("--pred", required=True)
    ap.add_argument("--gold", required=True)
    args = ap.parse_args()

    pred = load_rows(args.pred)
    gold = load_rows(args.gold)

    failures = defaultdict(list)  # field -> [request_id]
    for rid, grow in gold.items():
        prow = pred.get(rid)
        if prow is None:
            for f in FIELDS:
                failures[f].append(rid)
            continue
        res = compare_row(prow, grow)
        for f in FIELDS:
            if not res[f]:
                failures[f].append(rid)

    print("=" * 64)
    print(" FAILURE ANALYSIS")
    print("=" * 64)

    print("\n1) By field (most failing first):")
    for f, ids in sorted(failures.items(), key=lambda kv: -len(kv[1])):
        if ids:
            print(f"   {f:34} x{len(ids):<3} {', '.join(ids[:8])}")

    print("\n2) By request_type:")
    by_type = Counter()
    for rid, ids in failures.items():
        for r in ids:
            by_type[gold[r].get("request_type", "?")] += 1
    for t, n in by_type.most_common(5):
        print(f"   {t:24} x{n}")

    print("\n3) By gold affordability_status:")
    by_status = Counter()
    for f, ids in failures.items():
        for r in ids:
            by_status[gold[r].get("affordability_status", "?")] += 1
    for t, n in by_status.most_common(5):
        print(f"   {t:24} x{n}")

    print("\n4) Worst rows (most failing fields):")
    row_fail = Counter()
    for f, ids in failures.items():
        for r in ids:
            row_fail[r] += 1
    for r, n in row_fail.most_common(5):
        print(f"   {r} ({gold[r].get('request_type')}): {n}/7 fields wrong")

    print("\n5) Row diffs for worst rows:")
    for r, _ in row_fail.most_common(3):
        g, p = gold[r], pred.get(r, {})
        for f in FIELDS:
            gv, pv = g.get(f, ""), p.get(f, "") if p else ""
            if (gv or "").strip() != (pv or "").strip():
                print(f"   {r}.{f}:\n     gold: {str(gv)[:160]}\n     pred: {str(pv)[:160]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

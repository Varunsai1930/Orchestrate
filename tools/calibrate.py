"""Knob-search calibrator: find the forecast-model config that best matches
the 25 solved samples. Dev tool only — not part of the submission zip.
"""
import csv
import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

import state  # noqa: E402
from decider import decide  # noqa: E402
from evidence import extract_image_amounts, interpret_messages  # noqa: E402
from llm_client import get_client  # noqa: E402
from state import load_corpus  # noqa: E402

GOLD = {r["request_id"]: r for r in csv.DictReader(open(ROOT / "dataset" / "sample_requests.csv"))}


def asp_match(pred, gold):
    try:
        p, g = float(pred), float(gold)
    except (TypeError, ValueError):
        return 0.0
    return 1.0 if abs(p - g) <= max(1.0, 0.005 * max(abs(p), abs(g))) else 0.0


def run_config(corpus, llm, amendments):
    results = {}
    for rid, g in GOLD.items():
        try:
            st = state.build_state(corpus, g["user_id"], g["request_date"],
                                   amendments=list(amendments.values()))
            row = decide(g, corpus.options(rid), st)
            results[rid] = row
        except Exception as e:
            results[rid] = {"error": str(e)[:80]}
    return results


def score(results):
    """Full 7-field score per evaluation/score.py semantics (the real objective)."""
    sys.path.insert(0, str(ROOT / "code" / "evaluation"))
    from score import compare_row  # noqa: E402
    total = {"correct": 0, "n": 0}
    for rid, r in results.items():
        if "error" in r:
            continue
        res = compare_row(r, GOLD[rid])
        total["correct"] += sum(1 for v in res.values() if v)
        total["n"] += len(res)
    asp_ok = sum(asp_match(r.get("amount_safe_to_pay"), GOLD[rid]["amount_safe_to_pay"])
                 for rid, r in results.items() if "error" not in r)
    st_ok = sum(r.get("affordability_status") == GOLD[rid]["affordability_status"]
                for rid, r in results.items() if "error" not in r)
    m_ok = sum(r.get("recommended_payment_method") == GOLD[rid]["recommended_payment_method"]
               for rid, r in results.items() if "error" not in r)
    errors = [f"{rid}:{r['error']}" for rid, r in results.items() if "error" in r]
    return total["correct"], total["n"], asp_ok, st_ok, m_ok, errors


def main():
    corpus = load_corpus()
    llm = get_client("mock")
    amendments = {}
    amendments.update(interpret_messages(corpus, llm))
    amendments.update(extract_image_amounts(corpus, llm))

    grid = list(itertools.product(
        [False, True],                                # income_from_history
        ["projected", "exclude", "monthly_lump"],     # variables_mode
        ["max_median_last", "median", "last"],        # amount_rule
    ))
    rows = []
    for inc, var, amt in grid:
        state.configure(income_from_history=inc, variables_mode=var, amount_rule=amt)
        results = run_config(corpus, llm, amendments)
        tot, n, a, s, m, errors = score(results)
        rows.append((tot, n, a, s, m, inc, var, amt, errors))
        print(f"TOTAL={tot:>3}/{n} asp={a:>2}/25 status={s:>2}/25 method={m:>2}/25 | "
              f"income_hist={inc!s:5} vars={var:12} amt={amt:16} errors={len(errors)}")

    rows.sort(key=lambda r: (-r[0], -r[2], -r[3], -r[4]))
    best = rows[0]
    print(f"\nBEST: TOTAL={best[0]}/{best[1]} asp={best[2]} status={best[3]} method={best[4]} | "
          f"income_from_history={best[5]} variables_mode={best[6]} amount_rule={best[7]}")
    if best[8]:
        print("errors:", best[8][:5])


if __name__ == "__main__":
    main()

"""Buy or Wait? — entry point.

Reads dataset/, reconstructs financial state, interprets evidence (messages,
images) via describe-only LLM, decides deterministically, validates every row,
and writes the submission output.csv at the repo root.

Usage:
    python3 code/main.py                     # full dataset -> output.csv
    python3 code/main.py --samples           # 25 solved samples -> cache/output_samples.csv
    python3 code/main.py --offline           # reuse cached LLM evidence, no network
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import CACHE_DIR, DATA_DIR, OUTPUT_PATH  # noqa: E402
from decider import decide, fallback_row  # noqa: E402
from evidence import (extract_image_amounts, extract_salaries,  # noqa: E402
                      interpret_messages)
from llm_client import get_client  # noqa: E402
from state import build_state, load_corpus  # noqa: E402
from validator import OUTPUT_COLUMNS, validate_row  # noqa: E402


def run(requests_path, output_path, offline=False, log_path=None):
    t_start = time.time()
    corpus = load_corpus(DATA_DIR)
    llm = get_client("offline" if offline else None)

    amendments = {}
    amendments.update(interpret_messages(corpus, llm))
    amendments.update(extract_salaries(corpus, llm))
    amendments.update(extract_image_amounts(corpus, llm))
    # evidence transparency: injection-style content is flagged, surfaced in the
    # run summary, and never allowed to alter decisions (the decider ignores it)
    suspicious = [a for a in amendments.values() if a.get("suspicious")]

    with open(requests_path, newline="", encoding="utf-8-sig") as f:
        requests = list(csv.DictReader(f))

    rows, violations_log = [], []
    for request in requests:
        rid = request["request_id"]
        state = build_state(corpus, request["user_id"], request["request_date"],
                            amendments=list(amendments.values()))
        options = corpus.options(rid)
        row = decide(request, options, state)
        problems = validate_row(row, request, state.profile, options,
                                state.recurring_index())
        if problems:
            violations_log.append({"request_id": rid, "violations": problems})
            row = fallback_row(request, "; ".join(problems[:2]))
        rows.append(row)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    if log_path:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        Path(log_path).write_text(
            "\n".join(json.dumps(v) for v in violations_log), encoding="utf-8")

    return {"requests": len(rows), "violations": len(violations_log),
            "suspicious_evidence": len(suspicious),
            "output": str(out), "seconds": round(time.time() - t_start, 1)}


def main():
    ap = argparse.ArgumentParser(description="Buy or Wait? financial agent")
    ap.add_argument("--samples", action="store_true",
                    help="run the 25 solved samples instead of requests.csv")
    ap.add_argument("--output", default=None, help="override output path")
    ap.add_argument("--offline", action="store_true",
                    help="use cached LLM evidence only (no network)")
    args = ap.parse_args()

    if args.samples:
        summary = run(DATA_DIR / "sample_requests.csv",
                      args.output or CACHE_DIR / "output_samples.csv",
                      args.offline, CACHE_DIR / "run_log_samples.jsonl")
    else:
        summary = run(DATA_DIR / "requests.csv",
                      args.output or OUTPUT_PATH,
                      args.offline, CACHE_DIR / "run_log.jsonl")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

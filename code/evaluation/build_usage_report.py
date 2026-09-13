"""Generate evaluation/usage_report.md from usage_log.jsonl.

The PS requires this file in code.zip summarizing the FINAL full-dataset run:
providers, models, calls, tokens, totals and per-request averages, costs.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import USAGE_LOG  # noqa: E402

N_REQUESTS = 250


def main(log_path=USAGE_LOG, n_requests=N_REQUESTS, out_path=None):
    log_path = Path(log_path)
    rows = []
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    agg = defaultdict(lambda: {"calls": 0, "in": 0, "out": 0, "cost": 0.0, "provider": ""})
    for r in rows:
        a = agg[r.get("model", "unknown")]
        a["calls"] += r.get("calls", 1)
        a["in"] += r.get("input_tokens", 0)
        a["out"] += r.get("output_tokens", 0)
        a["cost"] += r.get("cost_usd", 0.0)
        a["provider"] = r.get("provider", "unknown")

    lines = ["# Token Usage and Cost Analysis", "",
             "Model usage behind the shipped `output.csv`: evidence generation "
             "(message/image/salary passes) plus the final full-dataset run, "
             "which replayed the evidence cache.", ""]
    if not rows:
        lines.append("_No model calls recorded (deterministic mock run or "
                     "evidence served entirely from cache)._")
        lines += ["", "| model | provider | calls | input tokens | output tokens | est. cost (USD) |",
                  "|---|---|---|---|---|---|"]
    else:
        lines += ["| model | provider | calls | input tokens | output tokens | est. cost (USD) |",
                  "|---|---|---|---|---|---|"]
        tot = {"calls": 0, "in": 0, "out": 0, "cost": 0.0}
        for model, a in sorted(agg.items()):
            lines.append(f"| {model} | {a['provider']} | {a['calls']} | {a['in']} | "
                         f"{a['out']} | ${a['cost']:.4f} |")
            tot["calls"] += a["calls"]
            tot["in"] += a["in"]
            tot["out"] += a["out"]
            tot["cost"] += a["cost"]
        lines.append(f"| **overall** |  | {tot['calls']} | {tot['in']} | {tot['out']} | ${tot['cost']:.4f} |")
        lines += ["", f"- Average tokens per request: {(tot['in'] + tot['out']) / max(1, n_requests):.0f} "
                  f"(input {tot['in'] / max(1, n_requests):.0f} / output {tot['out'] / max(1, n_requests):.0f})",
                  f"- Estimated cost per request: ${tot['cost'] / max(1, n_requests):.5f}"]

    report = "\n".join(lines) + "\n"
    out = Path(out_path) if out_path else Path(__file__).resolve().parent / "usage_report.md"
    out.write_text(report, encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

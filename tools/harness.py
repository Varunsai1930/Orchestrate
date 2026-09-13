"""One-command harness: clone-to-submission in a single run.

    python3 tools/harness.py            # full loop
    python3 tools/harness.py --quick    # skip tests + packaging

Stages (each gated; the harness exits non-zero on the first failure):
  preflight   python version, dataset present, evidence cache status
  pipeline    full 250-request run -> output.csv (offline: replays evidence cache)
  samples     25 solved samples -> field-level score vs gold
  tests       unittest suite (validator gate, eval math, gold self-score)
  package     code.zip + secrets assertion + artifact inventory
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def run(cmd, cwd=ROOT, timeout=300):
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr, round(time.time() - t0, 1)


def stage(name, ok, detail=""):
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}{(' - ' + detail) if detail else ''}")
    return ok


def main():
    ap = argparse.ArgumentParser(description="Buy or Wait? delivery harness")
    ap.add_argument("--quick", action="store_true", help="skip tests and packaging")
    args = ap.parse_args()
    results = []

    # ---- preflight
    data = ROOT / "dataset"
    files = ["requests.csv", "sample_requests.csv", "financial_profiles.csv",
             "financial_events.csv", "request_payment_options.csv",
             "exchange_rates.csv", "messages.csv", "images.csv"]
    missing = [f for f in files if not (data / f).exists()]
    media = len(list((data / "media" / "images").glob("*.png"))) if (data / "media" / "images").exists() else 0
    cache = ROOT / "cache" / "evidence.jsonl"
    cache_lines = sum(1 for _ in cache.open()) if cache.exists() else 0
    results.append(stage("preflight", not missing,
                         f"dataset {'ok' if not missing else 'MISSING ' + str(missing)}, "
                         f"{media} images, {cache_lines} cached evidence entries"))

    # ---- pipeline: full dataset
    rc, out, err, secs = run([PY, "code/main.py", "--offline"])
    summary = {}
    try:
        summary = json.loads(out)
    except json.JSONDecodeError:
        pass
    ok = rc == 0 and summary.get("requests") == 250 and summary.get("violations") == 0
    results.append(stage("pipeline", ok,
                         f"{summary.get('requests')} requests, {summary.get('violations')} violations, {secs}s"))
    if not ok and err:
        print(err[-500:])

    # ---- samples + score
    rc, out, err, _ = run([PY, "code/main.py", "--samples", "--offline"])
    rc2, out2, _, _ = run([PY, "code/evaluation/score.py", "--pred",
                           "cache/output_samples.csv", "--gold", "dataset/sample_requests.csv"])
    total = next((ln for ln in out2.splitlines() if "TOTAL" in ln), "?")
    ok = rc == 0 and rc2 == 0 and "175" in total
    results.append(stage("samples", ok, total.strip()))

    # ---- tests
    if not args.quick:
        rc, out, err, _ = run([PY, "-m", "unittest", "discover", "-s", "tests"], timeout=120)
        last = (out or err).strip().splitlines()[-1] if (out or err) else "?"
        results.append(stage("tests", rc == 0, last))

    # ---- package
    if not args.quick:
        rc, out, err, _ = run([PY, "tools/package.py"])
        ok = rc == 0 and "secrets check: clean" in out
        results.append(stage("package", ok, f"code.zip {ROOT.joinpath('code.zip').stat().st_size // 1024} KB" if ok else err[-200:]))

    # ---- artifact inventory
    out_csv = ROOT / "output.csv"
    rows = sum(1 for _ in out_csv.open()) - 1 if out_csv.exists() else 0
    log = (ROOT / "log.txt").exists()
    print(f"\nartifacts: output.csv {rows} rows | code.zip "
          f"{'present' if (ROOT / 'code.zip').exists() else 'MISSING'} | "
          f"log.txt {'present' if log else 'MISSING'}")

    failed = [r for r in results if not r]
    print(f"\nHARNESS {'PASS' if not failed else 'FAIL'}: "
          f"{len(results) - len(failed)}/{len(results)} stages green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

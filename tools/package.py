"""Build code.zip for submission (PS: code, prompts/config, README, evaluation/).

Excludes: dataset/, cache/, tools/, .env, log.txt, virtualenvs, __pycache__.
"""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "code.zip"

INCLUDE_DIRS = ["code", "tests"]
INCLUDE_FILES = ["README.md", "SOLUTION.md", "RUN.md", "CONTRACT.md", "decisions.md", "requirements.txt", "CLEANUP_REPORT.md", "ARCHITECTURE_REVIEW.md"]
EXCLUDE_PARTS = {"__pycache__", ".env", "dataset", "cache", "tools", "venv", ".git"}
EXCLUDE_SUFFIX = {".pyc", ".log"}
EXCLUDE_FILES = {"usage_log.jsonl"}


def main():
    if OUT.exists():
        OUT.unlink()
    count = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        # ship the evidence cache: derived artifacts of our own LLM passes (not
        # organizer data) — makes a cold grader run reproduce output.csv offline
        ev = ROOT / "cache" / "evidence.jsonl"
        if ev.exists():
            z.write(ev, "cache/evidence.jsonl")
            count += 1
        usage = ROOT / "code" / "evaluation" / "usage_log.jsonl"
        if usage.exists():
            z.write(usage, "code/evaluation/usage_log.jsonl")
            count += 1
        for d in INCLUDE_DIRS:
            for p in sorted((ROOT / d).rglob("*")):
                if not p.is_file():
                    continue
                if EXCLUDE_PARTS & set(p.parts) or p.suffix in EXCLUDE_SUFFIX:
                    continue
                if p.name in EXCLUDE_FILES:
                    continue
                z.write(p, p.relative_to(ROOT))
                count += 1
        for f in INCLUDE_FILES:
            p = ROOT / f
            if p.is_file():
                z.write(p, p.relative_to(ROOT))
                count += 1
    print(f"{OUT} written: {count} files, {OUT.stat().st_size / 1024:.0f} KB")
    # safety: never ship secrets
    with zipfile.ZipFile(OUT) as z:
        names = z.namelist()
        bad = [n for n in names if ".env" in n]
        assert not bad, f"SECRETS IN ZIP: {bad}"
    print("secrets check: clean")


if __name__ == "__main__":
    main()

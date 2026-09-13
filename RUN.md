# RUN.md — run the project yourself

Everything runs from this repo root. Python 3.10+ (stdlib only — nothing to install).
Optional: a `.env` at the repo root with `LLM_*` keys enables real LLM/VLM evidence
interpretation; without it everything runs in deterministic mock mode offline.

## 1. Score the full dataset (the submission artifact)

```bash
python3 code/main.py
```

What happens: loads `dataset/` (250 requests, 25,342 financial events, 275 profiles,
payment options, exchange rates), interprets evidence (cached — no API calls needed
after the first run), forecasts 90 days of balance per user, decides, validates every
row, and writes **`output.csv`** at the repo root.

Expected: `{"requests": 250, "violations": 0, ..., "seconds": ~0.3}` — zero rows fall
back; every row is a full decision.

Reproduce the submitted `output.csv` byte-for-byte (offline, no API key — the
shipped `cache/evidence.jsonl` inside code.zip replays our real LLM evidence):

```bash
python3 code/main.py --offline
```

Look at the answers:

```bash
head -5 output.csv
python3 -c "import csv; from collections import Counter; \
  print(Counter(r['affordability_status'] for r in csv.DictReader(open('output.csv'))))"
```

## 2. Verify against the 25 solved examples

```bash
python3 code/main.py --samples --offline
python3 code/evaluation/score.py --pred cache/output_samples.csv \
    --gold dataset/sample_requests.csv
```

Expected: a per-field scorecard (explanations 100%, spending changes 88%, …,
TOTAL = 129/175 (73.7%) with the shipped evidence) and a per-row failure list. The `--offline`
flag proves the decision pipeline needs **zero LLM calls** — evidence is cached in
`cache/evidence.jsonl`.

## 3. Dig into the failures

```bash
python3 code/evaluation/analyze.py --pred cache/output_samples.csv \
    --gold dataset/sample_requests.csv
```

Prints failure clusters by field, by request type, by status, the worst rows, and
row-level diffs — this is the loop we used to tune the forecast model.

## 4. Watch the safety check work

```bash
python3 - <<'EOF'
import sys; sys.path.insert(0, "code")
from state import load_corpus, build_state, simulate
corpus = load_corpus()
st = build_state(corpus, "user_06", "2026-01-03")
base = simulate(st).min_daily
lifted = simulate(st, changes=[("stop", "event_476", None, "streaming")]).min_daily
print(f"min balance without changes: {base:.2f}")
print(f"min balance after stopping streaming: {lifted:.2f}")
print(f"max safe today before changes: {base - st.minimum_balance:.2f}")
EOF
```

Stopping the EUR 19 streaming subscription lifts the whole 90-day balance curve —
that is exactly how `spending_changes_needed` unlocks payments (sample request_06).

## 5. Run the tests

```bash
python3 -m unittest discover -s tests -v
```

19 tests: the adversarial validator (all 25 gold rows must pass it), the eval
harness (self-score must be 100%), and hand-computed scoring cases.

## 6. Regenerate the ops report

```bash
python3 code/evaluation/build_usage_report.py
```

Rebuilds `code/evaluation/usage_report.md` from `code/evaluation/usage_log.jsonl`
— the token/cost record the problem statement requires in the submission.

## 7. Re-run with a real LLM (optional)

```bash
export LLM_PROVIDER=openai-compat
export LLM_API_KEY=sk-...
export LLM_BASE_URL=https://openrouter.ai/api/v1
export LLM_MODEL=nvidia/nemotron-3.5-lightning:free   # or any OpenAI-compatible model
export VLM_MODEL=inclusionai/ling-3.0-flash-vl:free   # vision, for the 16 images
mv cache/evidence.jsonl cache/evidence.jsonl.shipped  # keep the shipped cache
python3 code/main.py --samples   # re-interprets 215 messages + 16 images
```

All evidence is cached per content-hash + provider, so throttled runs resume where
they stopped, and `--offline` always replays the last complete pass.

## File map

| path | role |
|---|---|
| `code/main.py` | entry point — wiring only |
| `code/state.py` | financial state, recurring detection, 90-day simulator |
| `code/evidence.py` | messages/images → amendment JSON (describe-only LLM) |
| `code/decider.py` | candidate plans, safety, ranking, serialization |
| `code/validator.py` | adversarial output gate (CONTRACT.md §6) |
| `code/evaluation/` | scorer, failure analyzer, usage report |
| `CONTRACT.md` | single source of truth (module interfaces + decision rules) |
| `decisions.md` | the full decision log (D-001…) — the AI-judge interview script |

# Buy or Wait? — deterministic financial-affordability agent

HackerRank Orchestrate (September 2026) submission.

## Approach

~95% deterministic pipeline. The LLM/VLM never makes decisions — it only
structures *evidence* (multilingual messages, document images) into amendment
JSON. Everything else is pure code, which makes the system debuggable,
reproducible and defensible:

```
dataset/*.csv
  -> state.py          load + currency conversion + dedup/conflict resolution
                       + recurring-bill detection (calendar-anchored)
                       + 90-day daily balance simulator
  -> evidence.py       messages + images -> amendment JSON (describe-only LLM,
                       prompt-injection guard, disk-cached, replayable offline)
  -> decider.py        amount_safe_to_pay, earliest full-safe date, candidate
                       plans (full / partial / installments / wait, each with
                       permitted spending-change variants), 6-key ranking
                       per problem_statement.md, explanation templates
  -> validator.py      adversarial gate: schema, enums, bounds, option-exact
                       installment schedules, partial-payment rules, flexible-
                       only spending changes; invalid rows are replaced by a
                       conservative fallback (never shipped invalid)
  -> output.csv        one row per request, exact schema
  -> evaluation/       sample-based scorer, failure analyzer, usage report
```

## Setup

```bash
pip install nothing   # stdlib only; no third-party dependencies
```

Optional — real evidence interpretation needs an OpenAI-compatible endpoint
(OpenRouter, OpenAI, Z.ai, ...). Provide a `.env` at the repo root or export:

```text
LLM_PROVIDER=openai-compat
LLM_API_KEY=...            # keep out of the repo; .env is gitignored
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=...              # text model for messages
VLM_MODEL=...              # vision model for document images (defaults to LLM_MODEL)
```

Without a key everything runs in deterministic mock mode (no network).

## Run

```bash
python3 code/main.py              # full dataset -> output.csv (repo root)
python3 code/main.py --samples    # 25 solved samples -> cache/output_samples.csv
python3 code/main.py --offline    # reuse cached evidence; no network

# scoring against the solved samples
python3 code/evaluation/score.py --pred cache/output_samples.csv \
    --gold dataset/sample_requests.csv
python3 code/evaluation/analyze.py --pred cache/output_samples.csv \
    --gold dataset/sample_requests.csv

# tests (validator, eval harness)
python3 -m unittest discover -s tests -v
```

Evidence interpretation results are cached to `cache/evidence.jsonl` keyed by
content hash + provider, so re-runs after throttling never pay twice, and the
decider can be re-run offline (`--offline`) with zero LLM calls.

## Model calibration

The forecast model's composition (which flows count toward the 90-day
forecast) is decided by `tools/calibrate.py`, a knob search that maximizes the
full 7-field score on the 25 solved samples. The winning configuration lives
in `code/state.py` (`CONFIG`).

## Design decisions

See `decisions.md` — a running decision log (D-001..) kept during the build;
it feeds the AI-judge interview.

# Buy or Wait? — a deterministic financial-affordability agent

HackerRank Orchestrate (September 2026). For each of 250 financial requests,
the agent decides whether the user can safely afford an expense today — pay in
full, pay partially, use installments, wait, or not proceed — such that their
balance never drops below their preferred minimum across a 90-day forecast.

**Design principle: the LLM describes, deterministic code decides.** The model
only structures evidence (multilingual messages, scanned documents) into JSON.
Every amount, date and plan in `output.csv` is computed by stdlib-only code
that re-runs offline in 0.3s — and every row passes an adversarial validator
before it ships.

## Clone and run

```bash
git clone https://github.com/Varunsai1930/Orchestrate.git
cd Orchestrate

# full 250-request run -> output.csv (works offline; replays the shipped evidence cache)
python3 code/main.py

# reproduce the submitted predictions byte-for-byte
python3 code/main.py --offline

# score against the 25 organizer-solved samples
python3 code/main.py --samples --offline
python3 code/evaluation/score.py --pred cache/output_samples.csv --gold dataset/sample_requests.csv

# failure analysis, tests, one-command verification
python3 code/evaluation/analyze.py --pred cache/output_samples.csv --gold dataset/sample_requests.csv
python3 -m unittest discover -s tests -v
python3 tools/harness.py          # preflight -> pipeline -> samples -> tests -> package
```

Python 3.10+, standard library only — nothing to install. The repository ships
`cache/evidence.jsonl` (our LLM evidence extractions), so the commands above
reproduce the submitted `output.csv` with **zero API calls**. To re-generate
evidence live instead, add a `.env` with `LLM_*` variables (any
OpenAI-compatible endpoint; see RUN.md §7). Without it, everything still runs
in deterministic mock mode.

## Results (25 organizer-solved samples, field-level)

| field | accuracy |
|---|---|
| decision_explanation | 100% |
| spending_changes_needed | 88% |
| recommended_payment_method | 84% |
| payment_plan | 84% |
| affordability_status | 76% |
| earliest_date_for_full_payment | 64% |
| amount_safe_to_pay | 20% |
| **total** | **129/175 (73.7%)** |

Runtime 0.3s · 89 LLM calls · ~399K tokens · ~$0.002 total.

## How it works

```
dataset/*.csv ──> code/state.py      reconstruct finances: recurrence detection
                                     (calendar-anchored), dated FX conversion,
                                     conflict filters, 90-day daily simulator
     ──> code/evidence.py   messages + images -> structured amendment JSON
                            (describe-only LLM, injection guard, content-hash
                            cache, model failover, resumable)
     ──> code/decider.py    candidate plans (full / partial / installments per
                            option / wait, x permitted spending changes),
                            safety simulation, 6-key ranking per the spec
     ──> code/validator.py  adversarial gate: schema, enums, bounds, exact
                            option schedules, flexibility floors; invalid rows
                            are replaced by a logged conservative fallback
     ──> output.csv         250 rows, exact schema, 0 violations
     ──> code/evaluation/   field-level scorer, failure analyzer, token/cost report
```

## Repo map

| path | what it is |
|---|---|
| `problem_statement.md` | the challenge spec (organizer-provided) |
| `code/` | the solution (see the pipeline above) |
| `tests/` | 19 tests — validator rules, eval math, gold self-score |
| `tools/` | `harness.py` (one-command verification), `calibrate.py` (forecast knob search), `package.py`, evidence runners |
| `RUN.md` | step-by-step run guide with expected outputs |
| `SOLUTION_REPORT.md` | what was built, how it scores, and where the frontier is |
| `decisions.md` | 37-entry decision log — every architecture call, bet and measured reversal |
| `ARCHITECTURE_REVIEW.md` / `CLEANUP_REPORT.md` | honest self-audits: two audit rounds, 63 findings, all dispositioned |
| `cache/evidence.jsonl` | shipped LLM evidence extractions — offline reproduction without an API key |

## Credits

Dataset and challenge by HackerRank
([interviewstreet/hackerrank-orchestrate-september26](https://github.com/interviewstreet/hackerrank-orchestrate-september26)).
Built by Varun with Claude Code as the build orchestrator — see `log.txt` for
the full build transcript and `decisions.md` for every design decision.

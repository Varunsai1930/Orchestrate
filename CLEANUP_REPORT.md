# CLEANUP REPORT — dead code, duplicate logic, complexity

Two audit rounds were run: **round 1** by a dedicated read-only audit agent
(45 findings, verified against live reproductions and call-graph traces, not
guessing), and **round 2** re-auditing the codebase *after* the fixes. All
fixes were verified mechanically: 19/19 tests, and a byte-level diff of the
full 250-request output where **every changed row had to be explained**.

## Round 1 — findings and disposition (45 findings)

### Correctness bugs fixed (the audit's real payoffs)
| # | Severity | Finding | Fix |
|---|---|---|---|
| 1 | HIGH | `validator.py`: a leftover loop variable made the spending-change gate use the **last** change's floor for every event — admitting below-floor reduces *and* false-rejecting valid rows (both reproduced live) | per-event floor lookup keyed by `(reduce, event_id)` |
| 2 | HIGH | `decider.py`: wait candidates ignored `desired_completion_date` — 3 live rows recommended waits finishing a day late | deadline handling corrected; see D-034 for the final semantics (ranking preference, not a gate) |
| 3 | MED | Installment ranking ignored the **financing fee** (PS ranking rule 3: minimize total paid) | option `total_payable_amount` now feeds the ranking; the emitted plan still matches the option schedule exactly |
| 4 | MED | Blank `max_installment_months` was treated as "unlimited" — repo contract says blank = will not consider installments (119/275 profiles blank) | gate per contract |
| 5 | MED | One image-extraction failure would crash the whole 250-run mid-flight | transient failures leave the key uncached and retry on the next run |
| 6 | MED | `llm_client`: a malformed HTTP-200 response raised KeyError through the retry loop | guarded; model name now part of the evidence-cache tag so provider swaps recompute |

### Dead code removed
- `state.earliest_full_safe()` — duplicate of `decider._earliest_idx`, zero callers
- `State.extra_once_debits` — parameter, field and simulate branch always empty
- dead config branches (`variables_mode` exclude/monthly_lump, `amount_rule` variants) retained **only** as calibration knobs for `tools/calibrate.py` (documented; not reachable from the pipeline)
- unused imports (`os` in llm_client, `csv` in analyze, `CACHE_DIR/DATA_DIR` in evidence), unused `seconds` log field and its always-zero argument, dead `"key": None` placeholder, dead `fee_f`-style parsed fields that gained a consumer, the vestigial 120-iteration loop in `Corpus.rate()`, the dead `profile` parameter on `compare_row` (its check could never fire), dead `profile` parameter on `decide()`

### Duplicate logic collapsed to single homes
- amount parsing ×3 (`state._f`, `validator._num`, `score._num`) → `state.parse_amount`
- date parsing ×3 → `state.parse_date`
- plan/changes parsing ×2 (validator strict vs score lenient) → validator's strict parsers, imported by score
- tolerance constant ×2 → `config.AMOUNT_TOLERANCE` everywhere
- installment schedule reconstruction ×2 → validator `_match_option` now consumes the same pre-parsed Corpus fields the decider ranks on
- conservative fallback row ×2 → single home in `decider.fallback_row`
- user-amendment filtering ×2 → `build_state` only
- corpus options access ×2 → `corpus.options()`

### Unnecessary complexity removed
- `simulate()`: two-phase balance fold (init-to-balance, add deltas, subtract-back fold) rewritten as a single forward fold over the dated-flow dict — byte-equivalent output
- `load_corpus` try/except-NameError memoization replaced with a clean `_CORPUS = None` guard
- sys.path bootstraps retained deliberately (script-style entry points require them)

### Findings deliberately NOT applied (with reasons)
- **Contract divergence on `earliest_date_for_full_payment`** with with-changes plans: the internal validator is stricter than the PS text. Kept — a guaranteed-valid row beats marginal recall (D-019).
- **Skip general pass for employer messages** (would halve input tokens): employer messages also carry cancellations/delays; the salary pass is additive. Token cost is $0.001 total.
- **Per-message fallback retry amplification**: self-heals via cache; the shipped run replays the cache offline.
- **Amount formatting** `23.5` vs gold `23.50`: ground truth is numeric-tolerant; string-matching both styles is impossible (D-011).

## Verification of round 1
- 19/19 tests green after every batch of edits
- Full 250-run byte-diff vs pre-fix baseline: **9 rows** changed, all 1-cent float-accumulation-order artifacts of the simulate simplification (sub-tolerance), plus 3 rows corrected by the deadline rule — every changed row individually explained
- Sample score **119 → 124/175**: the fixes corrected real decisions, they didn't just clean code

## Round 2 — re-audit after the fixes

Round 2 was run by a second read-only agent over the cleaned codebase
(call-graph traces, regression hunting in the round-1 edits themselves,
CONTRACT.md-vs-code consistency). Result recorded below when complete.

## Round 2 — verdict and disposition

A second read-only agent re-audited the cleaned codebase (regression-hunting the
round-1 edits, CONTRACT-vs-code consistency, remaining duplicates).
**18 findings: 1 HIGH, 2 MED, 15 LOW (14 unique after one overlap).** All applied or dispositioned:

- **HIGH (round-1 regression, real):** `_log_usage` kept a 4-arg signature while
  its primary call site passed 3 — a TypeError on every successful JSON-mode
  completion, silently swallowed and *model-dependent* (models that reject JSON
  mode took the 4-arg fallback path and worked, which is why 46 salary facts
  still landed). Fixed to 3-arg everywhere and verified by a live call-path audit.
- **MED:** `max_safe_today()` became dead after the asp inlining — deleted along
  with its import. CONTRACT.md §3/§4 had drifted from the code in 7 places after
  calibration and rule reversals — rewritten to cite D-019/D-020/D-025/D-029/D-030.
- **LOW (14):** dead `fee_f` field (superseded by total_f pricing), `State.home`,
  `RecurringItem.description`, dead `abs_tol` parameter, dead `max_months and`
  conjunct, dead `_rank` lambda fallback, unused `cache=None` params, duplicated
  st_ok/m_ok computation in the calibrator, unused imports (harness, salary_filler,
  analyze), a MockProvider-crashing f-string in run_evidence, and duplicate
  decision IDs in decisions.md (renumbered D-032+).
- **Also from the deployment simulation:** validator's empty-earliest rule was
  stricter than the spec sentence ("leave it empty when the full amount is not
  expected to become safe within the forecast period") — relaxed to match the
  spec exactly; `affordable_now` still requires earliest == request_date.

**Round-2 verification:** 19/19 tests, harness 5/5 (preflight, pipeline 250/0
violations, samples, tests, package), and a **cold grader simulation**
(fresh zip + dataset, no env, no key) that reproduces the shipped `output.csv`
**byte-for-byte** via the default command. Final shipped state after the
salary-evidence refresh landed: **129/175 (73.7%)** on the solved samples.

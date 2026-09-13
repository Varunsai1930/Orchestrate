# ARCHITECTURE REVIEW — would I build it this way again, to win?

Honest post-mortem, written by the orchestrator. The question: with one
objective — win — is this the architecture I would choose? Short answer: **the
skeleton, yes, without hesitation. The time allocation and one subsystem, no —
and this report says exactly what I would do differently.**

## 1. The call I would make again: deterministic core, describe-only LLM

The hidden score compares exact amounts and dates across 250 requests × 7
fields. That single fact decides the architecture. An end-to-end LLM pipeline
("prompt with the user's finances, ask for the answer") produces confident
numbers that are wrong in ways you cannot debug, on a schedule you cannot
afford, and you cannot defend them in a 30-minute interview when the judge
asks "why is request_47's safe amount 12,510,645 and not 12,500,000?"

Our split — the LLM only structures evidence into JSON; a stdlib simulator,
decider and validator compute and gate everything — means:

- every number in `output.csv` is reproducible offline (proven byte-for-byte
  by a cold grader simulation),
- every wrong answer is diagnosable to a specific stage and a specific rule
  (the gold-pinned residual diagnostic did exactly that),
- the describe-only boundary means the model can be swapped, throttled, or
  removed entirely without touching a single decision.

If I were competing to win, I would not gamble the 30–40% output score on
stochastic reasoning. This is the part of the architecture I would keep
identically.

## 2. The parts I would keep, and why they win points

- **CONTRACT.md + file-ownership agent split.** Three workstreams never
  merged badly; the contract caught divergent assumptions before they shipped.
- **Adversarial validator + conservative fallback.** 0 invalid rows across
  every run, guaranteed structurally. An invalid row scores zero everywhere;
  this is direct expected-score protection, and it is a strong interview story.
- **Eval-first loop.** `score.py`/`analyze.py` existed before any decision
  logic. Every subsequent change was measured against the solved samples, and
  the loop caught two of my own regressions (an inverted metric, a 4-arg
  function that broke JSON-mode calls model-dependently).
- **Evidence caching keyed by content hash + provider.** Made every iteration
  cheap, survived throttling, survived model swaps, and made the submission
  reproducible by a grader with no API key.
- **The decision log.** 36 entries feeding the 30% interview: adopted rules,
  measured reversals, and the reasoning for every spec interpretation bet.

## 3. What I would do differently if winning were the only goal

### 3.1 The forecast forensics loop would start at hour 2, not hour 14
The dominant score loss is `amount_safe_to_pay` (20% on samples) and its
cascades — entirely a forecast-model problem, not an architecture problem. The
gold-pinned residual diagnostic (each solved sample pins the exact minimum of
the organizer's 90-day curve) was the single most informative tool we built,
and it arrived late. With a do-over: hour 2 builds a trivial end-to-end
baseline + the diagnostic; hours 3–14 are a per-user reverse-engineering grind
against 21 exact curve constraints, starting from the smallest users (user_13's
curve reconciles fully by hand). The infrastructure was "done enough" by hour
6; every marginal hour after that belonged to the forecast.

### 3.2 Parser-first evidence, LLM as fallback
Our evidence layer leaned on free-tier LLMs — and hit a 50-request daily cap
that blinded it for hours. The deeper mistake: the organizer's messages are
**templated machine-generated text** ("Gaji bulanan Anda naik menjadi IDR
42,750,000 berlaku mulai 2025-08-15"). For templated data, a deterministic
regex/date/amount parser extracts ~100% of facts with zero API calls, zero
rate limits, and zero hallucination risk; the LLM then handles only the
irregular tail. I would write the parser first and treat the model as
insurance. This one change removes the entire throttle saga and the evidence
coverage gaps that cost real points.

### 3.3 Finer-grained forecast knobs, earlier
The knob search operated at composition level (which categories project,
median vs last, lump vs per-occurrence). The residual analysis showed the
remaining error is per-stream: interleaved salary streams (user_11: a stable
monthly salary on the 15th plus varying mid-month payments) defeat a single
clusterer. A do-over splits income detection into per-stream models from the
start and calibrates per-category rather than globally.

### 3.4 Keep the spec-interpretation bets, but log them as bets
Two readings of the spec were genuine coin flips (deadline as ranking
preference vs eligibility gate; conservative `not_affordable` population). Both
were decided on textual evidence, both are documented with the arguments on
both sides (D-034/D-031), and neither costs anything on the public samples. I
would make the same bets — but I would also build a one-flag toggle to flip
them at submission time if any late evidence arrived.

## 4. The uncomfortable scoreboard

On the public solved samples the system finished at 129/175 (73.7%), with the
misses concentrated in the exact-match forecast fields. The architecture is
winner-compatible — nothing in it caps the score; the cap is how completely
the organizer's forecast model gets reverse-engineered. A winning run of this
architecture scores ~90%+ on `amount_safe_to_pay` by spending the hours we
spent on infrastructure hardening on data forensics instead. Conversely, the
"typical" alternative — one big prompt — would likely score worse on the
output (unverifiable numbers), and would have nothing to say in the interview
beyond "the model said so."

So: same skeleton, same validator and eval discipline, same agent pattern —
but parser-first evidence, forecast forensics from hour 2, and a paid API key
from minute one. That is the version I would bet on.

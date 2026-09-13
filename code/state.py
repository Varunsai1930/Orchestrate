"""Financial state reconstruction + 90-day balance simulator (CONTRACT.md §3).

Owner: Agent A (built by orchestrator after background agent infra failures).
Pure stdlib, deterministic. The LLM never touches this module.
"""
import csv
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

from config import DATA_DIR, FORECAST_DAYS

# Forecast-model knobs, tuned by tools/calibrate.py against the 25 solved samples.
# Defaults are the calibrated values; the calibrator overrides them in-process.
CONFIG = {
    "income_from_history": True,     # project settled salary history as recurring income
    "variables_mode": "projected",   # projected | exclude | monthly_lump
    "amount_rule": "median",           # max_median_last | median | last
}

VARIABLE_CATEGORIES = {"groceries", "transport", "dining", "shopping"}


def configure(**kw):
    CONFIG.update(kw)


# --------------------------------------------------------------------------- #
# Corpus loading
# --------------------------------------------------------------------------- #

def _rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [dict(r) for r in csv.DictReader(f)]


def parse_amount(value):
    """Tolerant numeric parse: strips commas/whitespace; None on garbage."""
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def parse_date(value):
    """ISO date parse; None on garbage."""
    try:
        return date.fromisoformat(str(value).strip())
    except (TypeError, ValueError):
        return None


class Corpus:
    def __init__(self, data_dir=DATA_DIR):
        data_dir = Path(data_dir)
        self.profiles = {r["user_id"]: r for r in _rows(data_dir / "financial_profiles.csv")}
        self.events = _rows(data_dir / "financial_events.csv")
        self.events_by_user = {}
        for e in self.events:
            e["amount_f"] = parse_amount(e["amount"])
            e["event_date_d"] = parse_date(e["event_date"])
            e["settlement_date_d"] = parse_date(e["settlement_date"]) or e["event_date_d"]
            e["min_allowed_f"] = parse_amount(e["minimum_allowed_amount"])
            self.events_by_user.setdefault(e["user_id"], []).append(e)
        self.options_by_request = {}
        for o in _rows(data_dir / "request_payment_options.csv"):
            o["payment_amount_f"] = parse_amount(o["payment_amount"])
            o["total_f"] = parse_amount(o["total_payable_amount"])
            o["n_payments_i"] = int(o["number_of_payments"]) if o["number_of_payments"] else 0
            o["freq_i"] = int(o["payment_frequency_days"]) if o["payment_frequency_days"] else 0
            o["first_date_d"] = parse_date(o["first_payment_date"])
            self.options_by_request.setdefault(o["request_id"], []).append(o)
        self.messages = _rows(data_dir / "messages.csv")
        self.images = _rows(data_dir / "images.csv")
        self.rates = {}
        for r in _rows(data_dir / "exchange_rates.csv"):
            self.rates[(r["rate_date"], r["from_currency"], r["to_currency"])] = float(r["rate"])
        self.rate_dates = sorted({k[0] for k in self.rates})

    def options(self, request_id):
        return self.options_by_request.get(request_id, [])

    def rate(self, on_date, from_cur, to_cur):
        """Rate for the pair on on_date; fallback: latest rate on or before it,
        then the inverse pair; None when the dataset supplies nothing."""
        if from_cur == to_cur:
            return 1.0
        key = (on_date.isoformat(), from_cur, to_cur)
        if key in self.rates:
            return self.rates[key]
        earlier = [rd for rd in self.rate_dates if rd <= on_date.isoformat()]
        if earlier:
            key = (earlier[-1], from_cur, to_cur)
            if key in self.rates:
                return self.rates[key]
        for (rd, f, t), rate in self.rates.items():
            if f == to_cur and t == from_cur and rd <= on_date.isoformat():
                return 1.0 / rate
        return None

    def to_home(self, amount, currency, on_date, home):
        if currency == home:
            return amount
        rate = self.rate(on_date, currency, home)
        if rate is None:
            # full rate coverage was verified on the shipped dataset; if this
            # ever fires on other data it means currency-scale corruption risk
            print(f"WARNING: no FX rate for {currency}->{home} on {on_date}; "
                  f"using stated amount unconverted", file=sys.stderr)
            return amount  # never invent a rate
        return amount * rate


_CORPUS = None


def load_corpus(data_dir=DATA_DIR):
    """Load once per process; later calls return the cached Corpus."""
    global _CORPUS
    if _CORPUS is None:
        _CORPUS = Corpus(data_dir)
    return _CORPUS


# --------------------------------------------------------------------------- #
# Recurrence detection
# --------------------------------------------------------------------------- #

def detect_recurring(events, as_of):
    """Deterministic recurrence over settled debits (and optionally income).

    Groups by (category, direction), then sub-clusters chronologically by
    amount similarity. A cluster is recurring when it has >=3 occurrences
    with a stable interval (5-95 days, +-5 tolerance). Returns list of dicts.
    Knobs (CONFIG): income_from_history, variables_mode, amount_rule.
    """
    groups = {}
    for e in events:
        if e["status"] != "settled" or e["amount_f"] is None:
            continue
        if e["event_date_d"] is None or e["event_date_d"] > as_of:
            continue
        if e["direction"] == "debit":
            if e["event_type"] not in ("expense", "subscription", "debt_payment"):
                continue
            if CONFIG["variables_mode"] == "exclude" and e["category"] in VARIABLE_CATEGORIES:
                continue
        elif e["direction"] == "credit":
            if not CONFIG["income_from_history"]:
                continue
            if e["event_type"] != "income":
                continue
        else:
            continue
        groups.setdefault((e["category"], e["direction"]), []).append(e)

    recurring = []
    for (category, direction), group in groups.items():
        group.sort(key=lambda e: e["event_date_d"])

        def emit(cluster):
            """Return a stream meta dict if the cluster is a stable cadence."""
            if len(cluster) < 3:
                return None
            dates = [e["event_date_d"] for e in cluster]
            diffs = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
            if not diffs:
                return None
            interval = int(statistics.median(diffs))
            if not (5 <= interval <= 95):
                return None
            # stable cadence: every gap within +-5 days of interval * k (k >= 1),
            # so a single missed month does not kill the stream
            if any(abs(d - interval * max(1, round(d / interval))) > 5 for d in diffs):
                return None
            amounts = [e["amount_f"] for e in cluster[-6:]]
            if CONFIG["amount_rule"] == "median":
                base_amount = statistics.median(amounts)
            elif CONFIG["amount_rule"] == "last":
                base_amount = amounts[-1]
            else:
                base_amount = max(statistics.median(amounts), amounts[-1])
            last = cluster[-1]
            lump = (CONFIG["variables_mode"] == "monthly_lump"
                    and category in VARIABLE_CATEGORIES and direction == "debit")
            if lump:
                cutoff = dates[-1] - timedelta(days=30)
                base_amount = sum(e["amount_f"] for e in cluster if e["event_date_d"] > cutoff)
                anchor = dates[-1] - timedelta(days=30)
                interval = 30
            else:
                anchor = dates[-1]
            return {
                "event_id": last["event_id"],
                "category": category,
                "direction": direction,
                "amount": base_amount,
                "currency": last["currency"],
                "interval_days": interval,
                "last_date": anchor,
                "flexibility": last["flexibility"] or "fixed",
                "minimum_allowed_amount": last["min_allowed_f"],
                "description": last["description"],
            }

        def split_on_gaps(cluster):
            """Cut a cluster wherever a gap exceeds 2.2x its median interval."""
            if len(cluster) < 3:
                return [cluster]
            dates = [e["event_date_d"] for e in cluster]
            diffs = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
            med = statistics.median(diffs)
            parts = [[cluster[0]]]
            for e, gap in zip(cluster[1:], diffs):
                if med and gap > 2.2 * med:
                    parts.append([e])
                else:
                    parts[-1].append(e)
            return parts

        def subcluster(group_, band):
            clusters_ = []
            for e in group_:
                placed = False
                for cluster in clusters_:
                    med = statistics.median([x["amount_f"] for x in cluster])
                    gap = (e["event_date_d"] - cluster[-1]["event_date_d"]).days
                    if gap <= 120 and band[0] * med <= e["amount_f"] <= band[1] * med:
                        cluster.append(e)
                        placed = True
                        break
                if not placed:
                    clusters_.append([e])
            return clusters_

        # run a tight amount band (separates dual streams and amount spikes) and
        # a loose band (tolerates drifting bill amounts); keep the pass that
        # explains more of the category's events with stable streams
        def try_pass(band):
            streams_, consumed = [], 0
            for c in subcluster(group, band):
                for part in split_on_gaps(c):
                    m = emit(part)
                    if m:
                        streams_.append(m)
                        consumed += len(part)
            # merge fragments that project onto the same payday (amount step-ups
            # split one stream in two; keep the most recent level)
            streams_.sort(key=lambda m: m["last_date"], reverse=True)
            kept = []
            for m in streams_:
                nxt = m["last_date"] + timedelta(days=m["interval_days"])
                if any(abs((nxt - (k["last_date"] + timedelta(days=k["interval_days"]))).days) <= 3
                       for k in kept):
                    consumed -= 1
                    continue
                kept.append(m)
            return kept, consumed / max(1, len(group))

        tight, tight_cov = try_pass((0.8, 1.25))
        loose, loose_cov = try_pass((0.6, 1.6))
        streams, _cov = (tight, tight_cov) if tight_cov >= loose_cov else (loose, loose_cov)

        # Safety guards on fragmentation:
        # - multiple debit streams from one category are usually one bill split by
        #   amount variance -> over-counted outflow; use the conservative merge
        # - interleaved semi-monthly credit fragments (e.g. salary on the 13th and
        #   the 30th) sum into one monthly income stream
        if len(streams) > 1:
            if direction == "debit":
                streams = loose if loose else streams
            else:
                ivs = [m["interval_days"] for m in streams]
                if max(ivs) / max(1, min(ivs)) < 1.5 and max(ivs) < 25:
                    merged = dict(streams[0])
                    merged["amount"] = sum(m["amount"] for m in streams)
                    merged["interval_days"] = 30
                    merged["last_date"] = min(m["last_date"] for m in streams)
                    streams = [merged]
        recurring.extend(streams)
    return recurring


def _add_months(d, k):
    month_index = d.month - 1 + k
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
                      else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


# --------------------------------------------------------------------------- #
# State building
# --------------------------------------------------------------------------- #

class RecurringItem:
    def __init__(self, meta, home, corpus):
        self.event_id = meta["event_id"]
        self.category = meta["category"]
        self.direction = meta["direction"]
        self.amount = corpus.to_home(meta["amount"], meta["currency"],
                                     meta["last_date"], home)
        self.interval_days = meta["interval_days"]
        self.last_date = meta["last_date"]
        self.flexibility = meta["flexibility"]
        self.minimum_allowed_amount = meta["minimum_allowed_amount"] or 0.0
        self.stopped = False
        self.override_amount = None  # from salary_change / reduce amendments

    def occurrences(self, start_date, days):
        """Future occurrence dates from last_date+interval through the window.

        Monthly cadences (25-35 days) project on the calendar day-of-month to
        avoid day-count drift; other cadences project by interval days.
        """
        out = []
        end = start_date + timedelta(days=days - 1)
        if 25 <= self.interval_days <= 35:
            k = 1
            while True:
                d = _add_months(self.last_date, k)
                if d > end:
                    break
                if d >= start_date:
                    out.append(d)
                k += 1
            return out
        k = 1
        while True:
            d = self.last_date + timedelta(days=self.interval_days * k)
            if d > end:
                break
            if d >= start_date:
                out.append(d)
            k += 1
        return out

    def effective_amount(self):
        if self.stopped:
            return 0.0
        if self.override_amount is not None:
            return max(self.override_amount, 0.0)
        return self.amount


class State:
    def __init__(self, profile, balance, recurring, scheduled, pending_debits,
                 request_date, minimum_balance, home):
        self.profile = profile
        self.balance = balance
        self.recurring = recurring          # [RecurringItem]
        self.scheduled = scheduled          # [(date, amount_home, direction, event_id)]
        self.pending_debits = pending_debits  # [(date, amount_home, event_id)]
        self.request_date = request_date
        self.minimum_balance = minimum_balance

    def recurring_index(self):
        return {r.event_id: {"flexibility": r.flexibility, "category": r.category,
                             "minimum_allowed_amount": r.minimum_allowed_amount,
                             "item": r}
                for r in self.recurring}


def build_state(corpus, user_id, request_date, amendments=()):
    request_date = parse_date(request_date) if isinstance(request_date, str) else request_date
    profile = corpus.profiles[user_id]
    home = profile["home_currency"]
    events = corpus.events_by_user.get(user_id, [])
    amendments = [a for a in amendments if a.get("user_id") in (None, user_id)]

    # event-level amendments by event_id
    amt_by_event, cancel_by_event, delay_by_event = {}, {}, {}
    salary_change, new_commitments = None, []
    for a in amendments:
        t = a.get("type")
        if t == "salary_change" and a.get("amount") is not None:
            salary_change = a
        elif t == "cancellation" and a.get("event_id"):
            cancel_by_event[a["event_id"]] = a
        elif t == "delay" and a.get("event_id") and a.get("effective_date"):
            delay_by_event[a["event_id"]] = a
        elif t == "amount" and a.get("event_id") and a.get("amount") is not None:
            amt_by_event[a["event_id"]] = a
        elif t == "new_commitment" and a.get("amount") is not None:
            new_commitments.append(a)

    def amt_of(e):
        if e["event_id"] in amt_by_event:
            a = amt_by_event[e["event_id"]]["amount"]
            if a is not None and a > 0:  # a 0/None extraction is not evidence
                return a
        if e["amount_f"] is not None:
            return e["amount_f"]
        return None  # blank and no image evidence: cannot treat as zero; ignore flow

    def settle_of(e):
        d = e["settlement_date_d"]
        if e["event_id"] in delay_by_event:
            nd = parse_date(delay_by_event[e["event_id"]].get("effective_date"))
            if nd:
                d = nd
        return d

    # lifecycle map for linked_event_id (PS: points to an earlier event in the
    # same transaction/investment lifecycle)
    excluded_ids = {e["event_id"] for e in events
                    if e["status"] in ("failed", "cancelled") or e["status"] == "unrealized"
                    or e["direction"] == "non_cash" or e["event_id"] in cancel_by_event}
    pending_credit_ids = {e["event_id"] for e in events
                          if e["status"] == "pending" and e["direction"] == "credit"}

    # scheduled / pending future flows (one-time, known)
    scheduled, pending_debits = [], []
    for e in events:
        if e["status"] in ("failed", "cancelled") or e["event_id"] in cancel_by_event:
            continue
        if e["direction"] == "non_cash" or e["status"] == "unrealized":
            continue
        # lifecycle safety: a future debit funded by a parent credit that is
        # itself excluded (e.g. a pending, unconfirmed sale) does not count —
        # never debit cash whose inflow is not confirmed.
        parent = e.get("linked_event_id")
        if (e["direction"] == "debit" and e["status"] == "scheduled" and parent
                and (parent in pending_credit_ids or parent in excluded_ids)):
            continue
        settle = settle_of(e)
        if settle is None or settle <= request_date:
            continue
        amount = amt_of(e)
        if amount is None:
            continue
        amount_home = corpus.to_home(amount, e["currency"], settle, home)
        if e["status"] == "pending":
            if e["direction"] == "debit":
                pending_debits.append((settle, amount_home, e["event_id"]))
            # pending credits are ignored until they settle (PS rule)
        elif e["status"] == "scheduled":
            scheduled.append((settle, amount_home, e["direction"], e["event_id"]))

    # salary change: adjust future scheduled income + recurring income
    if salary_change:
        eff = parse_date(salary_change.get("effective_date"))
        new_amt = salary_change["amount"]
        for i, (d, a, direction, eid) in enumerate(scheduled):
            if direction == "credit" and (eff is None or d >= eff):
                scheduled[i] = (d, new_amt, direction, eid)

    # recurring detection over settled history (debits only — see detect_recurring)
    recurring_meta = detect_recurring(events, request_date)

    # new commitments from evidence: recurring income (message-declared salary)
    # projects monthly from its effective date; one-time commitments are single flows.
    # Direction may be omitted by the model — infer from the message source:
    # employer statements of pay are income (credit), merchants/banks are debits.
    for c in new_commitments:
        eff = parse_date(c.get("effective_date")) or request_date
        amt_home = corpus.to_home(c["amount"], c.get("currency") or home, eff, home)
        direction = c.get("direction")
        if direction is None:
            src = str(c.get("source") or "")
            msg = next((m for m in corpus.messages if f"message:{m['message_id']}" == src), None)
            direction = "credit" if (msg or {}).get("source_type") == "employer" else "debit"
        if c.get("recurring") and direction == "credit":
            # First occurrence lands one full cycle out: a just-confirmed salary
            # pays at the NEXT cycle boundary, not on request day (D-025 — gold's
            # user_11 dip is exactly one month of bills before the first salary).
            anchor = eff if eff > request_date else request_date
            meta = {"event_id": c.get("event_id") or f"evidence:{c.get('source', 'msg')}",
                    "category": "salary", "direction": "credit", "amount": c["amount"],
                    "currency": c.get("currency") or home, "interval_days": 30,
                    "last_date": anchor - timedelta(days=30),
                    "flexibility": "fixed", "minimum_allowed_amount": None,
                    "description": c.get("note", "evidence salary")}
            recurring_meta.append(meta)
        elif eff <= request_date + timedelta(days=FORECAST_DAYS - 1):
            scheduled.append((eff, amt_home, direction, None))

    recurring = [RecurringItem(m, home, corpus) for m in recurring_meta]

    # A scheduled credit row IS the "next confirmed salary" (PS: count confirmed
    # salary on its settlement date). When salary history is too thin for
    # recurrence detection (<3 settled events), project it monthly from its date
    # — gold-verified on request_01 (prorated first salary + scheduled salary).
    hist_income_cats = {r.category for r in recurring if r.direction == "credit"}
    for d, a, dr, eid in scheduled:
        if dr != "credit" or eid is None:
            continue
        e = next((x for x in events if x["event_id"] == eid), None)
        cat = e["category"] if e else "salary"
        if cat in hist_income_cats:
            continue  # history recurrence already projects this stream
        recurring_meta.append({
            "event_id": eid, "category": cat, "direction": "credit",
            "amount": a, "currency": home, "interval_days": 30,
            "last_date": d, "flexibility": "fixed",
            "minimum_allowed_amount": None, "description": "scheduled salary",
        })
        recurring.append(RecurringItem(recurring_meta[-1], home, corpus))
        hist_income_cats.add(cat)

    for item in recurring:
        if item.event_id in cancel_by_event:
            item.stopped = True
        if item.direction == "credit" and salary_change:
            eff = parse_date(salary_change.get("effective_date"))
            if eff is None or item.last_date + timedelta(days=item.interval_days) >= eff:
                item.override_amount = salary_change["amount"]
        if item.event_id in delay_by_event:
            nd = parse_date(delay_by_event[item["event_id"]].get("effective_date"))
            if nd:
                shift = (nd - (item.last_date + timedelta(days=item.interval_days))).days
                if shift:
                    item.last_date = item.last_date + timedelta(days=shift)

    # drop projected income occurrences that duplicate a known scheduled credit (±3 days)
    sched_credits = [d for d, a, direction, eid in scheduled if direction == "credit"]
    for item in recurring:
        if item.direction != "credit":
            continue
        occ = item.occurrences(request_date, FORECAST_DAYS)
        for d in occ:
            if any(abs((d - s).days) <= 3 for s in sched_credits):
                item.suppressed_dates = getattr(item, "suppressed_dates", set()) | {d}

    return State(profile, float(profile["current_available_balance"]), recurring,
                 scheduled, pending_debits, request_date,
                 float(profile["minimum_balance_to_keep"]), home)


# --------------------------------------------------------------------------- #
# Simulation
# --------------------------------------------------------------------------- #

class SimResult:
    def __init__(self, daily, minimum_balance):
        self.daily = daily
        self.minimum_balance = minimum_balance
        self.min_daily = min(daily.values()) if daily else 0.0
        self.violation_dates = [d for d, v in daily.items() if v < minimum_balance - 1e-9]

    def ok(self):
        return not self.violation_dates


def simulate(state, changes=(), extra_debits=()):
    """Daily end-of-day balances for FORECAST_DAYS from state.request_date.

    changes: [("stop", event_id) | ("reduce_to", event_id, new_amount)]
    extra_debits: [(date, amount)] proposed request payments.
    """
    start = state.request_date
    flows = {}  # date -> net delta
    for d, amount, direction, eid in state.scheduled:
        flows[d] = flows.get(d, 0.0) + (amount if direction == "credit" else -amount)
    for d, amount, eid in state.pending_debits:
        flows[d] = flows.get(d, 0.0) - amount

    change_by_event = {}
    for c in changes:
        if c[0] == "stop":
            change_by_event[c[1]] = ("stop", None)
        else:
            change_by_event[c[1]] = ("reduce", c[2])

    for item in state.recurring:
        occ = item.occurrences(start, FORECAST_DAYS)
        suppressed = getattr(item, "suppressed_dates", set())
        change = change_by_event.get(item.event_id)
        stopped = item.stopped or (change and change[0] == "stop")
        if stopped:
            continue
        amount = item.effective_amount()
        if change and change[0] == "reduce":
            floor = item.minimum_allowed_amount or 0.0
            amount = min(amount, max(change[1], floor))
        for d in occ:
            if d in suppressed:
                continue
            delta = amount if item.direction == "credit" else -amount
            flows[d] = flows.get(d, 0.0) + delta

    for d, amount in extra_debits:
        d = parse_date(d) if isinstance(d, str) else d
        flows[d] = flows.get(d, 0.0) - amount

    # fold the dated deltas forward into cumulative end-of-day balances
    running = state.balance
    result_daily = {}
    for i in range(FORECAST_DAYS):
        running += flows.get(start + timedelta(days=i), 0.0)
        result_daily[i] = running
    return SimResult(result_daily, state.minimum_balance)



"""Decision engine (CONTRACT.md §4) — candidates, safety, ranking, serialization.

Deterministic: the LLM never runs here. Safety checks come from
state.simulate; amounts are computed, never guessed. Change tuples are
4-tuples: ("stop", event_id, None, category) / ("reduce_to", event_id,
amount, category) — state.simulate reads indexes 0-2, serialization 0-2,
explanations index 3.
"""
import itertools
from datetime import date as _date, timedelta

from state import simulate

DAY_ONE = 0


# --------------------------------------------------------------------------- #
# formatting helpers
# --------------------------------------------------------------------------- #

def _fmt_amount(v):
    """Plan/CSV format: round 2, integers bare, else shortest repr."""
    v = round(float(v) + 0.0, 2)
    return str(int(v)) if v == int(v) else repr(v)


def _fmt_money(v):
    """Comma-grouped money for explanations: 25,256 / 15,952,906.67."""
    v = round(float(v) + 0.0, 2)
    if v == int(v):
        return f"{int(v):,}"
    return f"{v:,.2f}"


def _serialize_plan(plan):
    if not plan:
        return "none"
    return "|".join(f"{d.isoformat()}:{_fmt_amount(a)}" for d, a in plan)


def _serialize_changes(changes):
    if not changes:
        return "none"
    return "|".join(f"stop:{c[1]}" if c[0] == "stop"
                    else f"reduce_to:{c[1]}:{_fmt_amount(c[2])}" for c in changes)


# --------------------------------------------------------------------------- #
# safety + candidate helpers
# --------------------------------------------------------------------------- #

def _earliest_idx(sim, amount, minimum):
    """First day index where paying `amount` keeps all later balances >= minimum."""
    for i in sorted(sim.daily):
        if min(v for j, v in sim.daily.items() if j >= i) - amount >= minimum - 1e-9:
            return i
    return None


def _considered(profile, method):
    return method in (profile.get("payment_methods_user_will_consider") or "").split("|")


def _plan_total(plan):
    return sum(a for _, a in plan)


def _eligible_changes(state, profile):
    """Single actions: stop / reduce-to-floor, honoring flexibility + willingness."""
    stop_cats = (profile.get("expense_categories_user_is_willing_to_stop") or "").split("|")
    reduce_cats = (profile.get("expense_categories_user_is_willing_to_reduce") or "").split("|")
    actions = []
    for item in state.recurring:
        if item.stopped or item.direction != "debit":
            continue
        flex = item.flexibility
        if flex in ("stoppable", "reducible_or_stoppable") and item.category in stop_cats:
            actions.append(("stop", item.event_id, None, item.category))
        if flex in ("reducible", "reducible_or_stoppable") and item.category in reduce_cats:
            floor = item.minimum_allowed_amount or 0.0
            if 0 < floor < item.amount - 0.01:
                actions.append(("reduce_to", item.event_id, floor, item.category))
    return actions


def _change_sets(actions, max_sets=60):
    """Singles, pairs, triples; one action per event; empty set first."""
    out = [()]
    seen = {()}
    for depth in (1, 2, 3):
        for combo in itertools.combinations(actions, depth):
            if len({c[1] for c in combo}) != len(combo):
                continue
            if combo not in seen:
                seen.add(combo)
                out.append(combo)
            if len(out) > max_sets:
                return out
    return out


# --------------------------------------------------------------------------- #
# explanations
# --------------------------------------------------------------------------- #

def _explain(method, request, profile, plan, changes):
    cur = profile["home_currency"]
    requested = float(request["requested_amount"])
    deadline = request["desired_completion_date"]
    min_bal = _fmt_money(float(profile["minimum_balance_to_keep"]))

    prefixes = []
    for c in changes:
        if c[0] == "stop":
            prefixes.append(f"Stop the {c[3]} expense")
        else:
            prefixes.append(f"Reduce the {c[3]} expense to {cur} {_fmt_money(c[2])}")
    prefix = (" and ".join(prefixes) + ", then ") if prefixes else ""

    if method == "not_recommended":
        return (f"Do not make this payment by {deadline}. None of the available "
                f"options keeps the {cur} {min_bal} minimum protected.")
    if method == "wait":
        d, amount = plan[0]
        return (f"Wait until {d.isoformat()}, then pay {cur} {_fmt_money(amount)} in full. "
                f"Paying sooner would put the {cur} {min_bal} minimum at risk.")
    if method == "installments":
        return (f"{prefix}Use {len(plan)} installments of {cur} {_fmt_money(plan[0][1])}, "
                f"starting {plan[0][0].isoformat()}. This leaves at least "
                f"{cur} {min_bal} available.")
    if method == "partial_payment":
        first, second = plan
        return (f"{prefix}Pay {cur} {_fmt_money(first[1])} today and the remaining "
                f"{cur} {_fmt_money(second[1])} on {second[0].isoformat()}. "
                f"This leaves at least {cur} {min_bal} available.")
    return (f"{prefix}Pay {cur} {_fmt_money(requested)} today. This leaves at least "
            f"{cur} {min_bal} available over the next 90 days.")


# --------------------------------------------------------------------------- #
# main decision
# --------------------------------------------------------------------------- #

def _add_candidate(cands, method, plan, changes, option_id=None):
    first_d = min(d for d, _ in plan)
    total = _plan_total(plan)
    cands.append({
        "method": method,
        "plan": sorted(plan),
        "changes": tuple(changes),
        "option_id": option_id,
        "_total": total, "_first": first_d, "_n": len(plan),
    })


def _rank(cands, deadline, rank_total):
    total = rank_total
    for c in cands:
        completes = all(d <= deadline for d, _ in c["plan"])
        c["key"] = (0 if completes else 1,
                    0 if not c["changes"] else 1,
                    total(c), c["_first"], c["_n"],
                    c["option_id"] or f"~{c['method']}")
    cands.sort(key=lambda c: c["key"])


def fallback_row(request, reason):
    """Deterministic conservative row when the validator rejects a decision."""
    return {
        "request_id": request["request_id"],
        "amount_safe_to_pay": "0",
        "affordability_status": "not_affordable",
        "recommended_payment_method": "not_recommended",
        "payment_plan": "none",
        "earliest_date_for_full_payment": "",
        "spending_changes_needed": "none",
        "decision_explanation": f"Conservative fallback: {reason}",
    }


def decide(request, options, state):
    profile = state.profile
    requested = round(float(request["requested_amount"]), 2)
    req_date = state.request_date
    deadline = request["desired_completion_date"]
    deadline = _date.fromisoformat(deadline) if isinstance(deadline, str) else deadline
    min_balance = state.minimum_balance
    allows_partial = str(request.get("allows_partial_payment", "")).lower() == "true"

    # no-changes curve drives both safe amounts and the earliest full date
    base_sim = simulate(state)

    # amount_safe_to_pay: no-changes curve, capped at requested (D-014)
    asp = round(min(max(0.0, base_sim.min_daily - min_balance), requested), 2)

    # earliest full-payment date on the no-changes curve (D-015)
    earliest_idx = _earliest_idx(base_sim, requested, min_balance)
    earliest_date = req_date + timedelta(days=earliest_idx) if earliest_idx is not None else None

    candidates = []
    considers_full = _considered(profile, "full_payment")

    # ---- full payment today, no changes
    if considers_full and earliest_idx == DAY_ONE:
        _add_candidate(candidates, "full_payment", [(req_date, requested)], ())

    actions = _eligible_changes(state, profile)
    change_sets = _change_sets(actions)

    # ---- with-change variant of full_payment only (D-019).
    # With-changes wait/partial candidates are never emitted: their plan dates
    # come from the changed curve, but earliest_date_for_full_payment reports
    # the no-changes date, which the validator (and gold style) forbids.
    if earliest_idx is not None:
        for cs in change_sets:
            if not cs:
                continue
            sim = simulate(state, changes=cs)
            e_idx = _earliest_idx(sim, requested, min_balance)
            if e_idx == DAY_ONE and considers_full:
                _add_candidate(candidates, "full_payment", [(req_date, requested)], cs)

    # ---- partial payment, no changes
    if (allows_partial and _considered(profile, "partial_payment")
            and 0 < asp < requested and earliest_date is not None
            and earliest_date <= deadline):
        plan = [(req_date, asp), (earliest_date, round(requested - asp, 2))]
        if simulate(state, extra_debits=plan).ok():
            _add_candidate(candidates, "partial_payment", plan, ())

    # ---- wait, no changes. NOT gated by the deadline: the PS gates only
    # partial_payment explicitly; for everything else deadline-completion is
    # ranking key 1 (a preference among eligible plans, else the key is
    # vacuous), and affordable_later is defined as "safe later" (D-030).
    if considers_full and earliest_idx is not None and earliest_idx > DAY_ONE:
        _add_candidate(candidates, "wait", [(earliest_date, requested)], ())

    # ---- installments, per supplied option (exact option schedule)
    max_months = (profile.get("max_installment_months") or "").strip()
    for opt in options or []:
        if (opt.get("payment_method") or "").strip() != "installments":
            continue
        if not _considered(profile, "installments"):
            continue
        if not max_months:  # blank = will not consider installments (repo contract)
            continue
        n, freq, first_d = opt["n_payments_i"], opt["freq_i"], opt["first_date_d"]
        if not n or not first_d or freq <= 0 or opt["payment_amount_f"] is None:
            continue
        last_d = first_d + timedelta(days=freq * (n - 1))
        months_touched = ((last_d.year - first_d.year) * 12
                          + (last_d.month - first_d.month) + 1)
        if months_touched > int(max_months):
            continue
        plan = [(first_d + timedelta(days=freq * k), round(opt["payment_amount_f"], 2))
                for k in range(n)]
        if simulate(state, extra_debits=plan).ok():
            _add_candidate(candidates, "installments", plan, (),
                           option_id=opt["payment_option_id"])
            for cs in change_sets:
                if not cs:
                    continue
                if simulate(state, changes=cs, extra_debits=plan).ok():
                    _add_candidate(candidates, "installments", plan, cs,
                                   option_id=opt["payment_option_id"])

    def _rank_total(c):
        # PS ranking rule 3: minimize the total amount paid. Installment plans
        # follow the option schedule, whose cost includes the financing fee
        # (payment_amount * n already prices it; total_payable is the authoritative sum when present).
        if c["method"] == "installments" and c["option_id"]:
            opt = next((o for o in (options or [])
                        if o["payment_option_id"] == c["option_id"]), None)
            if opt and opt.get("total_f"):
                return opt["total_f"]
        return c["_total"]

    if not candidates:
        return {
            "request_id": request["request_id"],
            "amount_safe_to_pay": _fmt_amount(asp),
            "affordability_status": "not_affordable",
            "recommended_payment_method": "not_recommended",
            "payment_plan": "none",
            "earliest_date_for_full_payment": "",
            "spending_changes_needed": "none",
            "decision_explanation": _explain("not_recommended", request, profile, [], ()),
        }

    _rank(candidates, deadline, _rank_total)
    chosen = candidates[0]

    if chosen["method"] == "wait":
        status = "affordable_later"
    elif chosen["method"] == "full_payment" and not chosen["changes"]:
        status = "affordable_now"
    else:
        status = "affordable_with_plan"

    return {
        "request_id": request["request_id"],
        "amount_safe_to_pay": _fmt_amount(asp),
        "affordability_status": status,
        "recommended_payment_method": chosen["method"],
        "payment_plan": _serialize_plan(chosen["plan"]),
        "earliest_date_for_full_payment":
            earliest_date.isoformat() if earliest_date else "",
        "spending_changes_needed": _serialize_changes(chosen["changes"]),
        "decision_explanation": _explain(chosen["method"], request, profile,
                                         chosen["plan"], chosen["changes"]),
    }

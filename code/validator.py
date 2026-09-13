"""Adversarial output validator — CONTRACT.md §6.

Every row written to output.csv must pass this. A rejected row is replaced by
the conservative fallback in main.py, so an invalid row can never reach the
hidden golden score. Pure functions, stdlib only.
"""
from datetime import date, timedelta

from config import AMOUNT_TOLERANCE
from state import parse_amount as _num, parse_date as _parse_date

STATUS_ENUM = {"affordable_now", "affordable_with_plan", "affordable_later", "not_affordable"}
METHOD_ENUM = {"full_payment", "partial_payment", "installments", "wait", "not_recommended"}
OUTPUT_COLUMNS = ["request_id", "amount_safe_to_pay", "affordability_status",
                  "recommended_payment_method", "payment_plan",
                  "earliest_date_for_full_payment", "spending_changes_needed",
                  "decision_explanation"]
TOL = 0.01


def _parse_plan(text):
    """Return [(date, amount)] or None on malformed input. 'none' -> []."""
    text = (text or "").strip()
    if text.lower() == "none":
        return []
    entries = []
    for part in text.split("|"):
        bits = part.strip().split(":")
        if len(bits) != 2:
            return None
        d, amt = _parse_date(bits[0]), _num(bits[1])
        if d is None or amt is None or amt < 0:
            return None
        entries.append((d, amt))
    return entries


def _parse_changes(text):
    """Return list of ('stop', eid) / ('reduce', eid, amount) or None malformed."""
    text = (text or "").strip()
    if text.lower() == "none":
        return []
    out = []
    for part in text.split("|"):
        bits = part.strip().split(":")
        if bits[0] == "stop" and len(bits) == 2:
            out.append(("stop", bits[1]))
        elif bits[0] == "reduce_to" and len(bits) == 3 and _num(bits[2]) is not None:
            out.append(("reduce", bits[1], _num(bits[2])))
        else:
            return None
    return out


def _close(a, b):
    return abs(a - b) <= max(1.0, AMOUNT_TOLERANCE * max(abs(a), abs(b)))


# Deliberately local: the gate and the engine are separate concerns; the
# helper is two lines and stable on both sides.
def _considers(profile, method):
    return method in (profile.get("payment_methods_user_will_consider") or "").split("|")


def validate_row(row, request, profile, options, recurring_index):
    """Return a list of violation strings; empty list = valid row."""
    v = []

    for col in OUTPUT_COLUMNS:
        if col not in row or row[col] is None:
            v.append(f"missing column {col}")
    if v:
        return v

    asp = _num(row["amount_safe_to_pay"])
    requested = _num(request.get("requested_amount"))
    status = (row["affordability_status"] or "").strip()
    method = (row["recommended_payment_method"] or "").strip()
    plan = _parse_plan(row["payment_plan"])
    earliest = _parse_date(row["earliest_date_for_full_payment"])
    changes = _parse_changes(row["spending_changes_needed"])
    req_date = _parse_date(request.get("request_date"))
    deadline = _parse_date(request.get("desired_completion_date"))

    if asp is None:
        v.append("amount_safe_to_pay not numeric")
    elif requested is not None and not (0 <= asp <= requested + TOL):
        v.append(f"amount_safe_to_pay {asp} outside [0, {requested}]")
    if status not in STATUS_ENUM:
        v.append(f"invalid affordability_status '{status}'")
    if method not in METHOD_ENUM:
        v.append(f"invalid recommended_payment_method '{method}'")
    if plan is None:
        v.append("malformed payment_plan")
    elif any(plan[i][0] >= plan[i + 1][0] for i in range(len(plan) - 1)):
        v.append("payment_plan not chronological")
    if changes is None:
        v.append("malformed spending_changes_needed")
    if req_date is None:
        v.append("request has unparsable request_date")
    if not (row["decision_explanation"] or "").strip():
        v.append("empty decision_explanation")
    if v:
        return v

    # ---- method-specific plan invariants (hold across all 25 solved samples)
    if method == "full_payment":
        if len(plan) != 1 or plan[0][0] != req_date or not _close(plan[0][1], requested):
            v.append("full_payment must be a single payment of requested_amount on request_date")
    if method == "partial_payment":
        if status != "affordable_with_plan":
            v.append("partial_payment requires affordability_status=affordable_with_plan")
        if len(plan) != 2:
            v.append("partial_payment requires exactly two payments")
        else:
            first, second = plan
            if first[0] != req_date or not _close(first[1], asp):
                v.append("first partial payment must be amount_safe_to_pay on request_date")
            if earliest is None or second[0] != earliest:
                v.append("second partial payment must fall on earliest_date_for_full_payment")
            if not _close(first[1] + second[1], requested):
                v.append("partial payments must sum to requested_amount")
        if str(request.get("allows_partial_payment", "")).lower() != "true":
            v.append("request does not allow partial payment")
        if not _considers(profile, "partial_payment"):
            v.append("user does not consider partial_payment")
        if not (0 < asp < requested):
            v.append("partial_payment requires 0 < amount_safe_to_pay < requested_amount")
        if earliest is not None and deadline is not None and earliest > deadline:
            v.append("earliest_date_for_full_payment after desired_completion_date")
    if method == "installments":
        if not _considers(profile, "installments"):
            v.append("user does not consider installments")
        matched = _match_option(plan, options)
        if matched is None:
            v.append("installment plan does not exactly match any supplied payment option")
    if method == "wait":
        if not _considers(profile, "full_payment"):
            v.append("wait requires the user to consider full_payment")
        if len(plan) != 1 or earliest is None or plan[0][0] != earliest \
                or not _close(plan[0][1], requested):
            v.append("wait must be a single payment of requested_amount on earliest_date_for_full_payment")
        if status != "affordable_later":
            v.append("wait requires affordability_status=affordable_later")
    if method == "not_recommended":
        if plan:
            v.append("not_recommended must have payment_plan=none")
        if status != "not_affordable":
            v.append("not_recommended requires affordability_status=not_affordable")

    # ---- cross-field invariants
    if status == "affordable_now":
        if earliest != req_date:
            v.append("affordable_now requires earliest_date_for_full_payment == request_date")
        if method != "full_payment":
            v.append("affordable_now requires recommended_payment_method=full_payment")
    if status == "not_affordable" and plan:
        v.append("not_affordable must have payment_plan=none")
    # Spec: "leave it empty when the full amount is not expected to become safe
    # within the forecast period" — legal for any status except affordable_now
    # (which requires earliest == request_date). A plan (installments/partial)
    # can complete a request whose lump-sum is never forecast-safe.
    if earliest is None and status == "affordable_later":
        v.append("affordable_later requires earliest_date_for_full_payment")

    # ---- spending changes
    seen = {}
    for change in changes:
        if change[0] == "stop":
            seen.setdefault(change[1], set()).add("stop")
        else:
            seen.setdefault(change[1], set()).add("reduce")
    if len(changes) > 3:
        v.append("more than three spending changes")
    for event_id, kinds in seen.items():
        if kinds == {"stop", "reduce"}:
            v.append(f"stop and reduce_to on the same event {event_id}")
        meta = (recurring_index or {}).get(event_id)
        if meta is None:
            v.append(f"spending change targets unknown event {event_id}")
            continue
        flex = meta.get("flexibility", "")
        category = meta.get("category", "")
        if "stop" in kinds and flex not in ("stoppable", "reducible_or_stoppable"):
            v.append(f"event {event_id} is not stoppable")
        if "reduce" in kinds and flex not in ("reducible", "reducible_or_stoppable"):
            v.append(f"event {event_id} is not reducible")
        if "stop" in kinds and category not in (profile.get("expense_categories_user_is_willing_to_stop") or "").split("|"):
            v.append(f"user is not willing to stop category {category}")
        if "reduce" in kinds and category not in (profile.get("expense_categories_user_is_willing_to_reduce") or "").split("|"):
            v.append(f"user is not willing to reduce category {category}")
        if "reduce" in kinds:
            floor = _num(meta.get("minimum_allowed_amount"))
            new_amount = next(c[2] for c in changes if c[0] == "reduce" and c[1] == event_id)
            if floor is not None and new_amount < floor - TOL:
                v.append(f"reduce_to {new_amount} below minimum_allowed_amount {floor} for {event_id}")

    return v


def _match_option(plan, options):
    """Return the payment_option_id whose schedule the plan exactly matches.

    Uses the pre-parsed Corpus fields (n_payments_i, first_date_d, freq_i,
    payment_amount_f) — the same parse path the decider ranks on.
    """
    for opt in options or []:
        if (opt.get("payment_method") or "").strip() != "installments":
            continue
        n = opt.get("n_payments_i") or 0
        start = opt.get("first_date_d")
        freq = opt.get("freq_i") or 0
        amt = opt.get("payment_amount_f")
        if n <= 0 or start is None or freq <= 0 or amt is None:
            continue
        schedule = [(start + timedelta(days=freq * k), amt) for k in range(n)]
        if len(schedule) == len(plan) and all(
            d1 == d2 and _close(a1, a2) for (d1, a1), (d2, a2) in zip(schedule, plan)
        ):
            return opt.get("payment_option_id")
    return None

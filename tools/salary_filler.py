"""Persistent salary-fact filler: one message per call, model failover, long
spacing. Runs until every employer message has a cached salary fact or the
time budget expires. Safe to re-run — cache is incremental.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from evidence import SALARY_SYSTEM, _load_cache, _norm, _store  # noqa: E402
from llm_client import content_hash, extract_json, get_client  # noqa: E402
from state import load_corpus  # noqa: E402

BUDGET_SECONDS = 21600  # 6h — spans the daily free-cap reset
PALETTE = [
    "nex-agi/nex-n2.5-mini:free",
    "poolside/laguna-s-2.1:free",
    "inclusionai/ling-3.0-flash-vl:free",
    "inclusionai/ling-3.0-flash-sante:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3.5-lightning:free",
]


def try_call(llm, model, listing):
    return extract_json(llm.complete(SALARY_SYSTEM, listing, model=model)) or {}


def main():
    corpus = load_corpus()
    llm = get_client()
    tag = "openai-compat:sal"
    employer = [m for m in corpus.messages if m.get("source_type") == "employer"]
    t_end = time.time() + BUDGET_SECONDS
    done_calls = 0

    while time.time() < t_end:
        cache = _load_cache()
        missing = []
        for m in employer:
            key = content_hash("sal", tag, m["message_id"], m["message_text"])
            if key not in cache:
                missing.append((m, key))
        if not missing:
            print(f"COMPLETE: all {len(employer)} employer messages resolved", flush=True)
            return
        print(f"missing {len(missing)} salary facts; next: {missing[0][0]['message_id']}", flush=True)
        m, key = missing[0]
        listing = (f"--- message_id: {m['message_id']} | sent_at: {m['sent_at']} ---\n"
                   f"{m['message_text']}")
        for model in PALETTE:
            try:
                parsed = try_call(llm, model, listing)
                done_calls += 1
            except Exception as e:
                print(f"  {model}: {type(e).__name__}, next model", flush=True)
                time.sleep(20)
                continue
            results = parsed.get("results", []) if isinstance(parsed, dict) else []
            r = next((x for x in results if isinstance(x, dict)
                      and x.get("message_id") == m["message_id"]), {})
            monthly = r.get("monthly_amount")
            if isinstance(monthly, (int, float)) and monthly > 0:
                value = _norm({
                    "type": "new_commitment", "amount": monthly,
                    "currency": r.get("currency"), "effective_date": r.get("effective_date"),
                    "direction": "credit", "recurring": bool(r.get("recurring", True)),
                    "note": f"salary evidence: {monthly} monthly",
                }, {"user_id": m.get("user_id") or None,
                    "request_id": m.get("request_id") or None,
                    "source": f"message:{m['message_id']}"})
            elif m["message_id"] in {x.get("message_id") for x in results if isinstance(x, dict)}:
                value = None  # well-formed: genuinely no salary fact
            else:
                print(f"  {model}: response missing message_id, next model", flush=True)
                time.sleep(15)
                continue
            _store(cache, key, value)
            print(f"  resolved {m['message_id']} via {model}: "
                  f"{'amount ' + str(monthly) if value else 'no salary fact'}", flush=True)
            time.sleep(8)  # stay polite with the shared pool
            break
        else:
            time.sleep(60)
    print(f"budget expired after {done_calls} calls", flush=True)


if __name__ == "__main__":
    main()

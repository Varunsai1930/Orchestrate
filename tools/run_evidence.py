"""Run the full evidence pass (messages + images) with the real provider.

Resumable: every result is cached to cache/evidence.jsonl, so this can be
re-run after throttling without paying for completed items.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from config import EVIDENCE_CACHE  # noqa: E402
from evidence import extract_image_amounts, extract_salaries, interpret_messages, _load_cache  # noqa: E402
from llm_client import get_client  # noqa: E402
from state import load_corpus  # noqa: E402


def count_cache():
    cache = _load_cache()
    msgs = sum(1 for v in cache.values() if v and str(v.get("source", "")).startswith("message:"))
    imgs = sum(1 for v in cache.values() if v and str(v.get("source", "")).startswith("image:"))
    return msgs, imgs


def main():
    corpus = load_corpus()
    llm = get_client()
    print(f"provider={llm.name} model={getattr(llm, 'base_url', '-')}", flush=True)

    # images first: only 16, and the blank-amount events block correct forecasts
    try:
        amounts = extract_image_amounts(corpus, llm)
        print(f"image amounts done: {json.dumps(amounts, default=str)[:600]}", flush=True)
    except Exception as e:
        print(f"image pass error: {type(e).__name__}: {e}", flush=True)

    msgs = interpret_messages(corpus, llm, batch_size=16)
    try:
        sal = extract_salaries(corpus, llm)
        print(f"salary pass done: {len(sal)} employer salary facts", flush=True)
    except Exception as e:
        print(f"salary pass error: {type(e).__name__}: {e}", flush=True)
    m, i = count_cache()
    print(f"messages done: {len(msgs)} interpreted (cache: {m} msgs, {i} imgs)", flush=True)
    print(f"cache: {EVIDENCE_CACHE}", flush=True)


if __name__ == "__main__":
    main()

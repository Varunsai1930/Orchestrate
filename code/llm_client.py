"""LLM/VLM client — describe-only usage, JSON outputs, usage logging.

The LLM NEVER makes financial decisions. It only structures evidence
(messages, images) into the amendment JSON defined in CONTRACT.md §5.
Every call is logged to code/evaluation/usage_log.jsonl for the required
token-usage report. Deterministic replay: all structured outputs are cached
by the caller (evidence.py), so decider/validator never call this.
"""
import base64
import hashlib
import json
import time
import urllib.error
import urllib.request

from config import (EVIDENCE_CACHE, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,
                    LLM_PROVIDER, MODEL_COSTS, USAGE_LOG, VLM_MODEL)


class LLMError(Exception):
    pass


class MockProvider:
    """Deterministic offline provider so the pipeline runs without keys."""
    name = "mock"

    def complete(self, system, user, images=None, model=None):
        if images:
            payload = {
                "type": "amount",
                "event_id": None,
                "amount": 0.0,
                "currency": None,
                "effective_date": None,
                "note": "mock image extraction (no provider configured)",
            }
        else:
            payload = {
                "type": "other",
                "event_id": None,
                "amount": None,
                "currency": None,
                "effective_date": None,
                "note": "mock message interpretation (no provider configured)",
            }
        return json.dumps(payload)


class OfflineProvider(MockProvider):
    """Cache-replay provider: tagged like the real provider so --offline reads the
    REAL evidence cache (mock entries can never collide). If a key is missing the
    mock output degrades gracefully instead of crashing. READ-ONLY: its outputs
    are never written to the cache, so a cache miss can never poison real keys."""
    name = "openai-compat"
    read_only = True


class OpenAICompatProvider:
    """OpenAI-style chat completions (OpenRouter, OpenAI, Z.ai, ...).

    Retries 429/5xx with backoff (free tiers rate-limit aggressively) and
    retries once without response_format for models that reject JSON mode.
    """
    name = "openai-compat"

    def __init__(self, base_url=None, api_key=None):
        self.base_url = (base_url or LLM_BASE_URL or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key or LLM_API_KEY
        self.model = LLM_MODEL  # part of the evidence cache tag (provider swaps recompute)

    def _post(self, body):
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}",
                     "X-Title": "Orchestrate-BuyOrWait"},
        )
        return urllib.request.urlopen(req, timeout=180)

    def complete(self, system, user, images=None, model=None, attempts=8):
        model = model or (VLM_MODEL if images else LLM_MODEL)
        content = [{"type": "text", "text": user}]
        for img_path in images or []:
            b64 = base64.b64encode(open(img_path, "rb").read()).decode()
            content.append({"type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"}})
        body = {
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content if (images or len(content) > 1) else user},
            ],
        }
        delay = 4.0
        for attempt in range(attempts):
            try:
                with self._post({**body, "response_format": {"type": "json_object"}}) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                _log_usage(model, body, data)
                return data["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as e:
                if e.code == 400:  # JSON mode unsupported -> plain request
                    try:
                        with self._post(body) as resp:
                            data = json.loads(resp.read().decode("utf-8"))
                        _log_usage(model, body, data)
                        return data["choices"][0]["message"]["content"]
                    except (urllib.error.HTTPError, KeyError, IndexError):
                        pass
                if e.code in (429, 500, 502, 503, 504) and attempt < attempts - 1:
                    retry_after = e.headers.get("Retry-After") if e.headers else None
                    time.sleep(float(retry_after) if retry_after else delay)
                    delay = min(delay * 1.7, 90.0)
                    continue
                raise
        raise LLMError(f"exhausted {attempts} attempts for {model}")


def _log_usage(model, request_body, response_data):
    usage = response_data.get("usage", {}) or {}
    tin = usage.get("prompt_tokens") or _est_tokens(json.dumps(request_body))
    tout = usage.get("completion_tokens") or _est_tokens(
        response_data["choices"][0]["message"]["content"])
    pin, pout = MODEL_COSTS.get(model, (1.0, 3.0))
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "provider": LLM_PROVIDER, "model": model,
        "calls": 1, "input_tokens": tin, "output_tokens": tout,
        "cost_usd": round(tin / 1e6 * pin + tout / 1e6 * pout, 6),
    }
    USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with USAGE_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def _est_tokens(text):
    return max(1, len(text) // 4)


def get_client(provider=None):
    provider = provider or LLM_PROVIDER
    if provider == "offline":
        return OfflineProvider()
    if provider == "mock":
        # Keyless default degrades to cache replay when the shipped evidence
        # cache exists: a cold run then reproduces the submitted output.csv
        # exactly (real interpretations, zero network). Mock entries can never
        # collide with the real provider's cache tag.
        if not LLM_API_KEY and EVIDENCE_CACHE.exists():
            return OfflineProvider()
        return MockProvider()
    return OpenAICompatProvider()


def extract_json(text):
    """Best-effort first-JSON-object extraction."""
    try:
        return json.loads(text)
    except Exception:
        pass
    import re
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def content_hash(*parts):
    h = hashlib.sha256()
    for p in parts:
        if isinstance(p, bytes):
            h.update(p)
        else:
            h.update(str(p).encode("utf-8"))
    return h.hexdigest()

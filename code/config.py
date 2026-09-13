"""Central configuration — paths, models, cost rates. Orchestrator-owned."""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "dataset"
MEDIA_DIR = DATA_DIR / "media" / "images"
CACHE_DIR = REPO_ROOT / "cache"
EVIDENCE_CACHE = CACHE_DIR / "evidence.jsonl"
USAGE_LOG = REPO_ROOT / "code" / "evaluation" / "usage_log.jsonl"
OUTPUT_PATH = REPO_ROOT / "output.csv"


def _load_dotenv(path=REPO_ROOT / ".env"):
    """Load KEY=VALUE pairs from .env (repo root) if present.

    Real values from the environment always win over .env. The file is
    gitignored and must never be committed (repo AGENTS.md §4).
    """
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

FORECAST_DAYS = 90
AMOUNT_TOLERANCE = 0.005  # 0.5% for eval comparisons

# Provider selection: env LLM_PROVIDER (mock|openai-compat), else mock for dev.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "mock")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
VLM_MODEL = os.environ.get("VLM_MODEL", LLM_MODEL)

# Rough USD cost per 1M tokens (input, output) — update per provider when known.
MODEL_COSTS = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "glm-4.5v": (0.6, 2.2),
    "glm-4.6": (0.6, 2.2),
    "nvidia/nemotron-3.5-lightning:free": (0.0, 0.0),
    "nex-agi/nex-n2.5-mini:free": (0.0, 0.0),
    "inclusionai/ling-3.0-flash-vl:free": (0.0, 0.0),
    "google/gemma-4-31b-it:free": (0.0, 0.0),
    "mock": (0.0, 0.0),
}

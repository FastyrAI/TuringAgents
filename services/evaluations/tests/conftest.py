import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
import ssl, certifi

ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv()

# Configure DeepEval exactly like VocalAi project - critical for caching
os.environ["DEEPEVAL_DISABLE_LOGGING"] = "true"  # Disable Confident AI logging (matches VocalAi)
# Note: Don't set DEEPEVAL_CACHE - let DeepEval use its defaults

try:
    import pytest  # type: ignore
    # Import DeepEval to initialize it properly
    import deepeval
except Exception:  # pragma: no cover
    pytest = None  # type: ignore
    deepeval = None  # type: ignore

# History persistence configuration - exactly like VocalAi (absolute paths)
DEEPEVAL_CACHE_FILE = "/Users/mac/Documents/project/TuringAgents/services/evaluations/.deepeval/.deepeval-cache.json"
DEEPEVAL_HISTORY_PATH = "/Users/mac/Documents/project/TuringAgents/services/evaluations/.deepeval/.deepeval-history.json"


def _read_existing_list():
    """Read existing evaluation history - matches VocalAi exactly."""
    if not os.path.exists(DEEPEVAL_HISTORY_PATH):
        return []
    try:
        with open(DEEPEVAL_HISTORY_PATH, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            return json.loads(content)
    except (json.JSONDecodeError, Exception):
        return []


def _write_list(data_list):
    """Write evaluation history - matches VocalAi exactly."""
    import pathlib
    pathlib.Path(DEEPEVAL_HISTORY_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(DEEPEVAL_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(data_list, f, ensure_ascii=False, indent=2)


def _append_to_list(new_entries):
    """Append to evaluation history - matches VocalAi exactly."""
    existing_list = _read_existing_list()
    
    if isinstance(new_entries, list):
        existing_list.extend(new_entries)
    else:
        existing_list.append(new_entries)
    
    _write_list(existing_list)


def _read_cache():
    """Read DeepEval cache file - matches VocalAi exactly."""
    if not os.path.exists(DEEPEVAL_CACHE_FILE):
        return None
    try:
        with open(DEEPEVAL_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def pytest_sessionstart(session):
    """Initialize session tracking - exactly like VocalAi."""
    session._deepeval_start_time = time.time()
    session._deepeval_counts = {"passed": 0, "failed": 0, "skipped": 0, "xfailed": 0, "xpassed": 0}
    session._deepeval_total = 0

    if os.path.exists(DEEPEVAL_CACHE_FILE):
        os.remove(DEEPEVAL_CACHE_FILE)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Track test results - matches VocalAi project."""
    outcome = yield
    rep = outcome.get_result()
    if rep.when != 'call':
        return

    sess = item.session
    sess._deepeval_total += 1
    if rep.outcome == "passed":
        sess._deepeval_counts["passed"] += 1
    elif rep.outcome == "failed":
        sess._deepeval_counts["failed"] += 1
    elif rep.outcome == "skipped":
        sess._deepeval_counts["skipped"] += 1

    if getattr(rep, "wasxfail", None):
        if rep.outcome == "passed":
            sess._deepeval_counts["xpassed"] += 1
        else:
            sess._deepeval_counts["xfailed"] += 1


def pytest_sessionfinish(session, exitstatus):
    """Capture results at end - exactly like VocalAi."""
    cache_data = _read_cache()
    if cache_data:
        _append_to_list(cache_data)
        print(f"✅ Appended evaluation results to history: {len(cache_data.get('test_cases_lookup_map', {}))} test cases")
    else:
        print("❌ No DeepEval cache data found")

def _make_gemini_model(model_name: str):
    from deepeval.models import GeminiModel  # type: ignore
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    return GeminiModel(model_name=model_name, api_key=key)

def _make_openai_model(model_name: str):  # pragma: no cover - optional
    from deepeval.models import OpenAIModel  # type: ignore
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    return OpenAIModel(api_key=key, model=model_name)

def _make_anthropic_model(model_name: str):  # pragma: no cover - optional
    from deepeval.models import AnthropicModel  # type: ignore
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return AnthropicModel(api_key=key, model=model_name)

if pytest is not None:  # pragma: no cover
    @pytest.fixture(scope="session")
    def deepeval_judge_model():
        """Create and return a single LLM-as-judge model instance per test session.

        Selection order:
        - EVAL_JUDGE_PROVIDER + EVAL_JUDGE_MODEL if set
        - Otherwise auto-detect by available API keys in order: GEMINI, OPENAI, ANTHROPIC
        """
        provider = (os.environ.get("EVAL_JUDGE_PROVIDER") or "gemini").strip().lower()
        model_name_env = (os.environ.get("EVAL_JUDGE_MODEL") or "").strip()

        # Auto-detect provider if not specified
        if not provider:
            if os.environ.get("GEMINI_API_KEY"):
                provider = "gemini"
            elif os.environ.get("OPENAI_API_KEY"):
                provider = "openai"
            elif os.environ.get("ANTHROPIC_API_KEY"):
                provider = "anthropic"

        # Defaults per provider
        if provider == "gemini":
            model_name = model_name_env or "gemini-1.5-pro"
            try:
                return _make_gemini_model(model_name)
            except Exception:
                pytest.skip("Judge credentials not configured for Gemini")
        elif provider == "openai":
            model_name = model_name_env or "gpt-4o-mini"
            try:
                return _make_openai_model(model_name)
            except Exception:
                pytest.skip("Judge credentials not configured for OpenAI")
        elif provider == "anthropic":
            model_name = model_name_env or "claude-3-5-sonnet-latest"
            try:
                return _make_anthropic_model(model_name)
            except Exception:
                pytest.skip("Judge credentials not configured for Anthropic")
        else:
            pytest.skip("Judge credentials not configured")


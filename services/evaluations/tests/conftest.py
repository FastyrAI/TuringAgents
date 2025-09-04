import os
import sys
from pathlib import Path
import ssl, certifi

ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv()
try:
    import pytest  # type: ignore
except Exception:  # pragma: no cover
    pytest = None  # type: ignore

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


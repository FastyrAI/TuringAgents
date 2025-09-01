import os
import sys
from pathlib import Path
import ssl, certifi

ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())

# Ensure tests can import the repo's 'services' namespace package
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Keep LLM env vars isolated during tests by default.
# If you want to use real provider keys from .env, set USE_DOTENV_FOR_TESTS=1
USE_DOTENV_FOR_TESTS = os.environ.get("USE_DOTENV_FOR_TESTS", "0").lower() in {"1", "true", "yes"}
if USE_DOTENV_FOR_TESTS:
    try:
        from dotenv import load_dotenv  # type: ignore
        # Ensure .env values override any empty placeholders
        load_dotenv(override=True)
    except Exception:
        pass
else:
    os.environ.setdefault("OPENAI_API_KEY", "")
    os.environ.setdefault("ANTHROPIC_API_KEY", "")
    os.environ.setdefault("GEMINI_API_KEY", "")

# Optional: auto-download NLTK corpora for metric tests when explicitly enabled
os.environ.setdefault("NLTK_DATA", str(Path.home() / "nltk_data"))
# Ensure NLTK sees the configured data directory on sys.path and auto-install wordnet if missing
try:
    import nltk  # type: ignore
    data_dir = os.environ.get("NLTK_DATA")
    if data_dir and data_dir not in nltk.data.path:
        nltk.data.path.append(data_dir)
    # Ensure download directory exists
    if data_dir:
        Path(data_dir).mkdir(parents=True, exist_ok=True)
    # Try loading; if missing, download quietly (no env var required)
    from nltk.corpus import wordnet  # type: ignore
    try:
        _ = wordnet.synsets("dog")
    except Exception:
        nltk.download("wordnet", quiet=True, download_dir=data_dir or None)  # type: ignore
        nltk.download("omw-1.4", quiet=True, download_dir=data_dir or None)  # type: ignore
except Exception:
    # If nltk isn't installed or download fails, tests will skip METEOR gracefully
    pass

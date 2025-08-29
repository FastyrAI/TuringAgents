import os

# Default threshold for DeepEval metrics; can be overridden via env
DEFAULT_THRESHOLD: float = float(os.getenv("DEEPEVAL_THRESHOLD", "0.5"))



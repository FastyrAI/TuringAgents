import os
from pathlib import Path
from typing import List, Dict, Any
from deepeval.models import GeminiModel

import pytest


# Optional import: skip whole module if deepeval not installed
deepeval = pytest.importorskip("deepeval", reason="deepeval not installed")
from deepeval.test_case import LLMTestCase
from deepeval.test_case import LLMTestCaseParams
from deepeval.metrics import GEval
from deepeval import evaluate
try:
    from deepeval import assert_test  # type: ignore
except Exception:  # pragma: no cover
    assert_test = None  # type: ignore


# Ensure repo root on sys.path similar to conftest
import sys
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from services.context_engineering.libs.summarize import Summarizer


def _read_json_or_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        pytest.fail(f"Dataset file not found: {path}")
    if path.suffix.lower() == ".jsonl":
        records: List[Dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    obj = __import__("json").loads(ln)
                except Exception as exc:  # pragma: no cover
                    pytest.fail(f"Invalid JSONL line in {path}: {exc}")
                if isinstance(obj, dict):
                    records.append(obj)
        return records
    with open(path, "r", encoding="utf-8") as f:
        data = __import__("json").load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
        return data["data"]
    pytest.fail(f"Unsupported JSON structure in {path}; expected list or {'data': [...]} object")
    return []


def _load_dataset() -> List[Dict[str, Any]]:
    env_path = os.environ.get("EVAL_FILE_SUMMARY") or os.environ.get("EVAL_DATA_FILE")
    if env_path:
        p = Path(env_path)
        print(f"Loading summary dataset from file: {p}")
        return _read_json_or_jsonl(p)

    if os.environ.get("EVAL_HF_DATASET") or os.environ.get("EVAL_CONFIDENT_DATASET"):
        pytest.fail(
            "HuggingFace / ConfidentAI dataset sources are not yet wired for this test. "
            "Please pass a local dataset with --json-file or --json-file-summary."
        )

    pytest.fail(
        "No dataset provided. Pass one of: --json-file, --json-file-summary, or per-task overrides."
    )
    return []


@pytest.mark.llm_judge
def test_summarize_deepeval_llm_judge_realtime(deepeval_judge_model):
    # Only run when an external judge is available and assert_test exists
    if assert_test is None:
        pytest.skip("DeepEval assert_test not available")
    if not any(os.environ.get(k) for k in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]):
        pytest.skip("Judge credentials not configured")

    dataset = _load_dataset()
    # Limit dataset size for cost: default 1 item (≈ keeps total evals small)
    max_items_str = os.environ.get("DEEPEVAL_JUDGE_ITEMS", "5")
    try:
        max_items = max(1, int(max_items_str))
    except Exception:
        max_items = 1
    dataset = dataset[:max_items]

    # Algorithms to evaluate. Default: ALL summarization algorithms
    algos_env = os.environ.get("DEEPEVAL_JUDGE_ALGORITHMS")
    if algos_env:
        algorithms_judge = [a.strip() for a in algos_env.split(",") if a.strip()]
        if not algorithms_judge:
            algorithms_judge = [
                "stuff",
                "refine",
                "map_reduce",
                "recursive",
                "hybrid_map_refine",
                "extractive",
                "ensemble",
            ]
    else:
        algorithms_judge = [
            "stuff",
            "refine",
            "map_reduce",
            "recursive",
            "hybrid_map_refine",
            "extractive",
            "ensemble",
        ]
    # Use shared session-scoped judge model
    judge_model = deepeval_judge_model

    # Build GEval metrics for LLM-as-judge
    faithfulness = GEval(
        name="Faithfulness",
        criteria=(
            "Does the summary make statements supported by the provided context only? "
            "Penalize unsupported claims, fabrications, or contradictions."
        ),
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.70,
        model=judge_model,
    )
    relevancy = GEval(
        name="Answer Relevancy",
        criteria=(
            "Does the summary directly address the input instruction/task and focus on relevant content?"
        ),
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.70,
        model=judge_model,
    )
    hallucination = GEval(
        name="Hallucination",
        criteria=(
            "Identify any content in the summary that is not grounded in the provided context. "
            "Higher score means fewer or no hallucinations."
        ),
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.70,
        model=judge_model,
    )
    metrics = [faithfulness, relevancy, hallucination]
    # Optional: allow selecting subset of metrics via env, e.g. "faithfulness,relevancy"
    which_metrics = os.environ.get("DEEPEVAL_JUDGE_METRICS")
    if which_metrics:
        selected = {m.strip().lower() for m in which_metrics.split(",") if m.strip()}
        name_to_metric = {
            "faithfulness": faithfulness,
            "relevancy": relevancy,
            "answer relevancy": relevancy,
            "hallucination": hallucination,
        }
        metrics = [name_to_metric[n] for n in selected if n in name_to_metric] or metrics

    s = Summarizer()

    test_cases: List[LLMTestCase] = []
    for record in dataset:
        user_input = str(record.get("input", "Summarize"))
        context_text = str(record.get("context", ""))
        combined_input = f"{user_input}\n\nContext:\n{context_text}" if context_text else user_input

        for algo in algorithms_judge:
            if algo == "stuff":
                summary = __import__("asyncio").run(s.stuff([context_text]))
            elif algo == "refine":
                summary = __import__("asyncio").run(s.refine([context_text]))
            elif algo == "map_reduce":
                summary = __import__("asyncio").run(s.map_reduce([context_text]))
            elif algo == "recursive":
                summary = __import__("asyncio").run(s.recursive([context_text]))
            elif algo == "hybrid_map_refine":
                summary = __import__("asyncio").run(s.hybrid_map_refine([context_text]))
            elif algo == "extractive":
                summary = __import__("asyncio").run(s.extractive([context_text]))
            elif algo == "ensemble":
                summary = __import__("asyncio").run(s.ensemble([context_text]))
            else:
                summary = __import__("asyncio").run(s.map_reduce([context_text]))

            case = LLMTestCase(
                input=combined_input,
                actual_output=summary,
            )
            test_cases.append(case)

    # Assert per case with the judge (single pass to avoid duplicate judge calls)
    for case in test_cases:
        assert_test(case, metrics)  # type: ignore



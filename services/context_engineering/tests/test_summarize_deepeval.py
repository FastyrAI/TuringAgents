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


def _load_dataset() -> List[Dict[str, Any]]:
    # Built-in tiny synthetic dataset; no env required
    return [
        {
            "input": "Summarize the order and shipment details.",
            "context": (
                "Alice Johnson placed order 12345 on 2024-07-01. "
                "Shipment to NYC expected in 3-5 days. Payment captured."
            ),
        },
        {
            "input": "Provide a concise report.",
            "context": (
                "Meeting discussed budget of $12,500 approved on 2024-06-30; next steps: hire PM; "
                "deadline in 2 weeks."
            ),
        },
    ]


 


@pytest.mark.llm_judge
def test_summarize_deepeval_llm_judge_realtime():
    # Only run when an external judge is available and assert_test exists
    if assert_test is None:
        pytest.skip("DeepEval assert_test not available")
    if not any(os.environ.get(k) for k in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]):
        pytest.skip("Judge credentials not configured")

    dataset = _load_dataset()
    # Limit dataset size for cost: default 1 item (≈ keeps total evals small)
    max_items_str = os.environ.get("DEEPEVAL_JUDGE_ITEMS", "1")
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
    judge_model = GeminiModel(
        model_name="gemini-2.5-flash",
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

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



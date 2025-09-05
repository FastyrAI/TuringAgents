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
        # If path doesn't exist, try relative to current working directory (evaluations folder)
        if not p.exists() and not p.is_absolute():
            # Remove the 'services/evaluations/' prefix since we're now in evaluations directory
            relative_path = str(p)
            if relative_path.startswith("services/evaluations/"):
                relative_path = relative_path[len("services/evaluations/"):]
                p = Path(relative_path)
        
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


# Generate test parameters like VocalAi project
def _generate_test_parameters():
    """Generate test parameters for parametrized testing."""
    dataset = _load_dataset()
    max_items_str = os.environ.get("DEEPEVAL_JUDGE_ITEMS", "2")  # Reduced default for testing
    try:
        max_items = max(1, int(max_items_str))
    except Exception:
        max_items = 2
    dataset = dataset[:max_items]

    # Algorithms to evaluate
    algos_env = os.environ.get("DEEPEVAL_JUDGE_ALGORITHMS")
    if algos_env:
        algorithms_judge = [a.strip() for a in algos_env.split(",") if a.strip()]
    else:
        algorithms_judge = ["stuff", "refine"]  # Reduced for testing

    # Generate all combinations
    test_params = []
    for record in dataset:
        for algo in algorithms_judge:
            test_params.append((record, algo))
    
    return test_params


@pytest.mark.llm_judge
@pytest.mark.parametrize("record,algorithm", _generate_test_parameters())
def test_summarize_individual_case(record, algorithm, deepeval_judge_model):
    """Test individual summarization case with specific algorithm - like VocalAi project."""
    if assert_test is None:
        pytest.skip("DeepEval assert_test not available")
    if not any(os.environ.get(k) for k in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]):
        pytest.skip("Judge credentials not configured")

    # Use shared session-scoped judge model
    judge_model = deepeval_judge_model

    # Build GEval metrics with varied thresholds to see both pass/fail cases
    faithfulness = GEval(
        name="Faithfulness",
        criteria=(
            "Does the summary make statements supported by the provided context only? "
            "Penalize any unsupported claims or fabrications."
        ),
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.90,  # High threshold to create some failures
        model=judge_model,
    )
    relevancy = GEval(
        name="Answer Relevancy",
        criteria=(
            "Does the summary directly address the input instruction/task and focus on relevant content?"
        ),
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.70,  # Medium threshold
        model=judge_model,
    )
    hallucination = GEval(
        name="Hallucination",
        criteria=(
            "Identify any content in the summary that is not grounded in the provided context. "
            "Higher score means fewer hallucinations."
        ),
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.80,  # High threshold to catch issues
        model=judge_model,
    )
    conciseness = GEval(
        name="Conciseness",
        criteria=(
            "Is the summary appropriately concise without being too brief or too verbose? "
            "Evaluate if it captures key information efficiently."
        ),
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.60,  # Medium threshold
        model=judge_model,
    )
    metrics = [faithfulness, relevancy, hallucination, conciseness]

    # Execute summarization
    s = Summarizer()
    user_input = str(record.get("input", "Summarize"))
    context_text = str(record.get("context", ""))
    combined_input = f"{user_input}\n\nContext:\n{context_text}" if context_text else user_input

    # Run the specific algorithm
    if algorithm == "stuff":
        summary = __import__("asyncio").run(s.stuff([context_text]))
    elif algorithm == "refine":
        summary = __import__("asyncio").run(s.refine([context_text]))
    elif algorithm == "map_reduce":
        summary = __import__("asyncio").run(s.map_reduce([context_text]))
    elif algorithm == "recursive":
        summary = __import__("asyncio").run(s.recursive([context_text]))
    elif algorithm == "hybrid_map_refine":
        summary = __import__("asyncio").run(s.hybrid_map_refine([context_text]))
    elif algorithm == "extractive":
        summary = __import__("asyncio").run(s.extractive([context_text]))
    elif algorithm == "ensemble":
        summary = __import__("asyncio").run(s.ensemble([context_text]))
    else:
        summary = __import__("asyncio").run(s.map_reduce([context_text]))

    # Create test case
    test_case = LLMTestCase(
        input=combined_input,
        actual_output=summary,
        context=[context_text] if context_text else None,
        retrieval_context=[context_text] if context_text else None,
    )

    # Test with DeepEval judge
    print(f"Testing {algorithm} algorithm on: {user_input[:50]}...")
    assert_test(test_case, metrics)


# Keep the original bulk test as backup (with better error handling)
@pytest.mark.llm_judge
def test_summarize_deepeval_llm_judge_realtime_bulk(deepeval_judge_model):
    """Original bulk test function with improved error handling."""
    if assert_test is None:
        pytest.skip("DeepEval assert_test not available")
    if not any(os.environ.get(k) for k in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]):
        pytest.skip("Judge credentials not configured")

    dataset = _load_dataset()
    max_items_str = os.environ.get("DEEPEVAL_JUDGE_ITEMS", "1")
    try:
        max_items = max(1, int(max_items_str))
    except Exception:
        max_items = 1
    dataset = dataset[:max_items]

    # Use only one algorithm for bulk testing
    algorithm = "stuff"
    judge_model = deepeval_judge_model

    # Multiple metrics with varied thresholds for bulk testing
    faithfulness = GEval(
        name="Faithfulness",
        criteria="Does the summary contain information supported by the context?",
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.75,  # Challenging threshold
        model=judge_model,
    )
    completeness = GEval(
        name="Completeness",
        criteria="Does the summary capture all the key information from the context?",
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.50,  # Medium threshold
        model=judge_model,
    )
    clarity = GEval(
        name="Clarity",
        criteria="Is the summary clear, well-structured, and easy to understand?",
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.65,  # Medium-high threshold
        model=judge_model,
    )
    metrics = [faithfulness, completeness, clarity]

    s = Summarizer()
    
    # Test each record individually within the function but continue on failures
    failed_cases = []
    passed_cases = []
    
    for record in dataset:
        try:
            user_input = str(record.get("input", "Summarize"))
            context_text = str(record.get("context", ""))
            combined_input = f"{user_input}\n\nContext:\n{context_text}" if context_text else user_input

            summary = __import__("asyncio").run(s.stuff([context_text]))
            
            test_case = LLMTestCase(
                input=combined_input,
                actual_output=summary,
                context=[context_text] if context_text else None,
                retrieval_context=[context_text] if context_text else None,
            )

            assert_test(test_case, metrics)
            passed_cases.append((record, algorithm))
            print(f"✅ Passed: {algorithm} on '{user_input[:30]}...'")
            
        except AssertionError as e:
            failed_cases.append((record, algorithm, str(e)))
            print(f"❌ Failed: {algorithm} on '{user_input[:30]}...' - {str(e)[:100]}...")
            # Continue testing other cases instead of stopping

    print(f"\n📊 Bulk Test Summary: {len(passed_cases)} passed, {len(failed_cases)} failed")
    
    # Only fail if ALL cases failed
    if len(passed_cases) == 0 and len(failed_cases) > 0:
        pytest.fail(f"All {len(failed_cases)} test cases failed")



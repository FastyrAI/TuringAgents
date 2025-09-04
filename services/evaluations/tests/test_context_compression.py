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
try:
    from deepeval import assert_test  # type: ignore
except Exception:  # pragma: no cover
    assert_test = None  # type: ignore

# Ensure repo root on sys.path similar to conftest
import sys
import json
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.context_engineering.libs.summarize import Summarizer  # type: ignore


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
                    obj = json.loads(ln)
                except Exception as exc:  # pragma: no cover
                    pytest.fail(f"Invalid JSONL line in {path}: {exc}")
                if isinstance(obj, dict):
                    records.append(obj)
        return records
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
        return data["data"]
    pytest.fail(f"Unsupported JSON structure in {path}; expected list or {'data': [...]} object")
    return []


def _load_context_dataset() -> List[Dict[str, Any]]:
    # Priority: task-specific path > global path
    env_path = os.environ.get("EVAL_FILE_CONTEXT") or os.environ.get("EVAL_DATA_FILE")
    if env_path:
        p = Path(env_path)
        print(f"Loading context dataset from file: {p}")
        return _read_json_or_jsonl(p)

    # If other dataset sources were requested, instruct user to pass file for now
    if os.environ.get("EVAL_HF_DATASET") or os.environ.get("EVAL_CONFIDENT_DATASET"):
        pytest.fail(
            "HuggingFace / ConfidentAI dataset sources are not yet wired for this test. "
            "Please pass a local dataset with --json-file or --json-file-context."
        )

    pytest.fail(
        "No dataset provided. Pass one of: --json-file, --json-file-context, "
        "or use per-task overrides."
    )
    return []


def _create_progressive_contexts(dataset: List[Dict[str, Any]], checkpoints: List[int]) -> Dict[int, str]:
    progressive_contexts: Dict[int, str] = {}
    for checkpoint in checkpoints:
        if checkpoint <= len(dataset):
            contexts = [item["context"] for item in dataset[:checkpoint]]
            progressive_contexts[checkpoint] = "\n\n".join(contexts)
    return progressive_contexts


@pytest.mark.llm_judge
def test_context_engineering_deepeval_progressive(deepeval_judge_model):
    if assert_test is None:
        pytest.skip("DeepEval assert_test not available")
    if not any(os.environ.get(k) for k in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]):
        pytest.skip("Judge credentials not configured")

    dataset = _load_context_dataset()

    max_items_str = os.environ.get("DEEPEVAL_CONTEXT_ITEMS", "5")
    try:
        max_items = max(1, int(max_items_str))
    except Exception:
        max_items = 5
    dataset = dataset[:max_items]

    checkpoints_env = os.environ.get("DEEPEVAL_CONTEXT_CHECKPOINTS", "2,3,5")
    try:
        checkpoints = [int(x.strip()) for x in checkpoints_env.split(",") if x.strip()]
        checkpoints = [c for c in checkpoints if c <= len(dataset)]
    except Exception:
        checkpoints = [2, 3, min(5, len(dataset))]
    if not checkpoints:
        checkpoints = [len(dataset)]

    anchor_idx = int(os.environ.get("DEEPEVAL_ANCHOR_IDX", "0"))
    anchor_idx = min(anchor_idx, len(dataset) - 1)

    thr_faith = float(os.environ.get("DEEPEVAL_FAITHFULNESS_THRESHOLD", "0.40"))
    thr_rel = float(os.environ.get("DEEPEVAL_RELEVANCY_THRESHOLD", "0.35"))
    thr_prec = float(os.environ.get("DEEPEVAL_PRECISION_THRESHOLD", "0.35"))

    judge_model = deepeval_judge_model

    faithfulness = GEval(
        name="Faithfulness",
        criteria=(
            "Does the answer use information that can be found in the provided context? "
            "Give partial credit for answers that contain some supported information. "
            "Only heavily penalize completely fabricated or contradictory information."
        ),
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=thr_faith,
        model=judge_model,
    )
    relevancy = GEval(
        name="Answer Relevancy",
        criteria=(
            "Does the answer attempt to address the question asked? "
            "Give credit for partial answers and reasonable interpretations. "
            "Only penalize completely irrelevant responses."
        ),
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=thr_rel,
        model=judge_model,
    )
    precision = GEval(
        name="Information Precision",
        criteria=(
            "Does the answer provide useful information related to the question? "
            "Give credit for reasonable attempts to answer even if not perfectly precise. "
            "Focus on whether the response contains meaningful content rather than perfect specificity."
        ),
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=thr_prec,
        model=judge_model,
    )
    contextual_coverage = GEval(
        name="Contextual Coverage",
        criteria=(
            "Does the answer demonstrate that relevant context was successfully retrieved and used? "
            "Give credit for answers that show understanding of the provided context, even if not perfect. "
            "Focus on whether the system successfully found and utilized relevant information."
        ),
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.30,
        model=judge_model,
    )
    metrics = [faithfulness, contextual_coverage]

    which_metrics = os.environ.get("DEEPEVAL_CONTEXT_METRICS")
    if which_metrics:
        selected = {m.strip().lower() for m in which_metrics.split(",") if m.strip()}
        name_to_metric = {
            "faithfulness": faithfulness,
            "relevancy": relevancy,
            "answer relevancy": relevancy,
            "precision": precision,
            "information precision": precision,
            "contextual_coverage": contextual_coverage,
            "contextual coverage": contextual_coverage,
        }
        metrics = [name_to_metric[n] for n in selected if n in name_to_metric] or metrics

    from services.context_engineering.libs.context_compression import ContextCompression  # type: ignore
    from services.context_engineering.libs.config import get_settings  # type: ignore
    from services.context_engineering.libs.router import LLMRouter  # type: ignore
    try:
        api = ContextCompression(get_settings())
        _ = api.graph.sample_node_count()
    except Exception as e:  # pragma: no cover
        pytest.skip(f"Graph not reachable: {e}")
    router = LLMRouter()

    progressive_contexts = _create_progressive_contexts(dataset, checkpoints)

    test_cases: List[LLMTestCase] = []
    anchor_results = []

    for checkpoint in checkpoints:
        cumulative_context = progressive_contexts[checkpoint]
        session_id = f"prog-{os.getpid()}-{__import__('time').time_ns()}-{checkpoint}"
        for j in range(min(checkpoint, len(dataset))):
            api.ingest(dataset[j]["context"], session_id=session_id)

        for i in range(min(checkpoint, len(dataset))):
            record = dataset[i]
            question = record["question"].strip()
            expected = str(record.get("expected_output", "")).strip()

            top_k = int(os.environ.get("DEEPEVAL_K", "20"))
            items = api.retrieve(question, session_id=session_id, k=top_k)
            node_texts = [it["text"] for it in items] if items else []
            if len(node_texts) < 8:
                node_texts.append(cumulative_context)
            numbered = "\n".join(f"[S{k+1}] {t}" for k, t in enumerate(node_texts))

            qa_prompt = (
                "Answer the question using only the provided context. "
                "If the answer is not stated or if the context shows the required condition is not met (e.g., no common category), return exactly 'Not enough information'. "
                "Return only the answer string with no extra words. Do not infer.\n\n"
                f"Question: {question}\n\nContext:\n{numbered}"
            )
            actual_output = __import__("asyncio").run(
                router.generate(qa_prompt, priority="P1", context_len=len(qa_prompt))
            )

            actual_str = (str(actual_output) or "").strip()

            combined_input = f"Question: {question}\n\nContext:\n{numbered}"
            case = LLMTestCase(
                input=combined_input,
                actual_output=actual_str,
                expected_output=expected,
            )
            test_cases.append(case)

            if i == anchor_idx:
                anchor_correct = (
                    (expected.lower() == "not enough information" and "not enough" in str(actual_output).lower())
                    or (expected and expected.lower() in str(actual_output).lower())
                )
                anchor_results.append({
                    "checkpoint": checkpoint,
                    "algorithm": "qa",
                    "actual": str(actual_output),
                    "expected": expected,
                    "correct": anchor_correct,
                    "question": question,
                })

    print(f"\n🧪 Testing {len(test_cases)} cases with real context engineering model...")
    for i, case in enumerate(test_cases, 1):
        print(f"   Evaluating case {i}/{len(test_cases)}...")
        assert_test(case, metrics)  # type: ignore

    if len(anchor_results) >= 2:
        print(f"\n🎯 Anchor Question Analysis:")
        print(f"   Question: '{dataset[anchor_idx]['question']}'")
        print(f"   Expected: '{dataset[anchor_idx]['expected_output']}'")
        print(f"   Algorithm: {anchor_results[0]['algorithm']}")
        first_correct = anchor_results[0]["correct"]
        last_correct = anchor_results[-1]["correct"]
        drift = (last_correct - first_correct) * 100
        print(f"   Drift: {drift:+.1f}%")
        for result in anchor_results:
            status = "✅" if result["correct"] else "❌"
            print(f"   Checkpoint {result['checkpoint']}: {status} '{result['actual']}' (expected: '{result['expected']}')")
        responses = [r['actual'] for r in anchor_results]
        unique_responses = set(responses)
        consistency_pct = (len(responses) - len(unique_responses) + 1) / len(responses) * 100
        print(f"   Consistency: {consistency_pct:.1f}% ({len(unique_responses)} unique responses)")


@pytest.mark.llm_judge
def test_context_engineering_end_to_end_pipeline_deepeval(deepeval_judge_model):
    if assert_test is None:
        pytest.skip("DeepEval assert_test not available")
    if not any(os.environ.get(k) for k in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]):
        pytest.skip("Judge credentials not configured")

    from services.context_engineering.libs.context_compression import ContextCompression  # type: ignore
    from services.context_engineering.libs.config import get_settings  # type: ignore

    try:
        api = ContextCompression(get_settings())
        _ = api.graph.sample_node_count()
    except Exception as e:  # pragma: no cover
        pytest.skip(f"Graph not reachable: {e}")

    session_id = f"e2e-{os.getpid()}-{__import__('time').time_ns()}"

    judge_model = deepeval_judge_model
    thr_e2e_faith = float(os.environ.get("DEEPEVAL_E2E_FAITHFULNESS_THRESHOLD", "0.25"))
    thr_e2e_rel = float(os.environ.get("DEEPEVAL_E2E_RELEVANCY_THRESHOLD", "0.25"))

    faithfulness = GEval(
        name="Faithfulness",
        criteria=(
            "Does the answer contain information that can be traced back to the provided context? "
            "Give partial credit for answers that use some context information. "
            "Only heavily penalize completely fabricated information."
        ),
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=thr_e2e_faith,
        model=judge_model,
    )
    relevancy = GEval(
        name="Answer Relevancy",
        criteria=(
            "Does the summary directly address the input instruction/task and focus on relevant content?"
        ),
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=thr_e2e_rel,
        model=judge_model,
    )
    metrics = [faithfulness, relevancy]

    dataset = _load_context_dataset()
    ds5 = dataset[: min(5, len(dataset))]
    for rec in ds5:
        api.ingest(rec["context"], session_id=session_id)

    from services.context_engineering.libs.router import LLMRouter  # type: ignore
    router = LLMRouter()

    thr_e2e_prec = float(os.environ.get("DEEPEVAL_E2E_PRECISION_THRESHOLD", "0.25"))
    precision_qa = GEval(
        name="Information Precision",
        criteria=(
            "Does the answer contain any relevant information, even if imperfect? "
            "Give high credit for any meaningful response that attempts to address the question. "
            "Only fail completely nonsensical or empty responses."
        ),
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=thr_e2e_prec,
        model=judge_model,
    )
    contextual_coverage_qa = GEval(
        name="Contextual Coverage",
        criteria=(
            "Does the answer demonstrate use of the retrieved context? "
            "Reward answers that reference or align with the provided snippets."
        ),
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.30,
        model=judge_model,
    )
    qa_metrics = [faithfulness, contextual_coverage_qa]
    which_metrics_qa = os.environ.get("DEEPEVAL_E2E_QA_METRICS") or os.environ.get("DEEPEVAL_CONTEXT_METRICS")
    if which_metrics_qa:
        selected = {m.strip().lower() for m in which_metrics_qa.split(",") if m.strip()}
        name_to_metric = {
            "faithfulness": faithfulness,
            "relevancy": relevancy,
            "answer relevancy": relevancy,
            "precision": precision_qa,
            "information precision": precision_qa,
            "contextual_coverage": contextual_coverage_qa,
            "contextual coverage": contextual_coverage_qa,
        }
        qa_metrics = [name_to_metric[n] for n in selected if n in name_to_metric] or qa_metrics

    for idx, rec in enumerate(ds5, 1):
        question = str(rec.get("question", "")).strip()
        expected = str(rec.get("expected_output", "")).strip()

        qa_k = int(os.environ.get("DEEPEVAL_K", "20"))
        qa_items = api.retrieve(question, session_id=session_id, k=qa_k)
        assert qa_items, f"no retrieval for dataset q{idx}: '{question[:60]}...'"
        node_texts = [it["text"] for it in qa_items]
        if len(node_texts) < 8:
            node_texts.append(rec["context"])  # include raw record context as fallback
        numbered = "\n".join(f"[S{k+1}] {t}" for k, t in enumerate(node_texts))

        qa_prompt = (
            "Answer the question using only the provided context. "
            "If the answer is not stated, return exactly 'Not enough information'. "
            "If the answer is present, return the exact phrase as it appears in context (full official name if applicable). "
            "Return only the answer string with no extra words. Do not infer.\n\n"
            f"Question: {question}\n\nContext:\n{numbered}"
        )
        answer = __import__("asyncio").run(router.generate(qa_prompt, priority="P1", context_len=len(qa_prompt)))
        answer_s = (str(answer) or "").strip()

        print(f"   Question {idx}: {question[:60]}...")
        print(f"   Expected: {expected}")
        print(f"   Actual: {answer_s}")
        print(f"   Context length: {len(numbered)} chars")

        combined_input_qa = f"Question: {question}\n\nContext:\n{numbered}"
        case_qa = LLMTestCase(
            input=combined_input_qa,
            actual_output=answer_s,
            expected_output=expected,
        )
        assert_test(case_qa, qa_metrics)  # type: ignore



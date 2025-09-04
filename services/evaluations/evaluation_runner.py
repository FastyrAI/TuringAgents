from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Set


def _project_root() -> Path:
    # services/evaluations/deepeval_runner.py → up 2 to repo root
    return Path(__file__).resolve().parents[2]


def _resolve_deepeval_tests(tasks: Set[str]) -> List[str]:
    root = _project_root()
    eval_tests = root / "services" / "evaluations" / "tests"

    tests: List[str] = []
    if "summary" in tasks:
        tests.append(str(eval_tests / "test_summarization.py"))
    if "context-compression" in tasks:
        tests.append(str(eval_tests / "test_context_compression.py"))
    if "graph" in tasks:
        tests.append(f"{eval_tests / 'test_context_compression.py'}::test_context_engineering_end_to_end_pipeline_deepeval")

    # Filter to only DeepEval-marked tests at collection time
    return tests


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="deepeval-runner",
        description="Run only DeepEval-marked tests with optional dataset/bounds",
    )
    parser.add_argument("--tasks", type=str, default="context-compression,summary")
    parser.add_argument("--items", type=int, default=None)
    parser.add_argument("--checkpoints", type=str, default=None)
    parser.add_argument("--report", type=str, default=None)
    parser.add_argument("--json-report", type=str, default=None)
    parser.add_argument("--verbose", action="store_true")

    # Dataset sources (one required): local JSON/JSONL, HuggingFace, or ConfidentAI id
    parser.add_argument("--json-file", dest="json_file", type=str, default=None, help="Path to JSON/JSONL dataset")
    parser.add_argument("--file", dest="json_file", type=str, default=None, help="Alias for --json-file")
    parser.add_argument("--json-file-context", dest="json_file_context", type=str, default=None)
    parser.add_argument("--json-file-summary", dest="json_file_summary", type=str, default=None)
    parser.add_argument("--json-file-graph", dest="json_file_graph", type=str, default=None)
    parser.add_argument("--huggingface-dataset", dest="hf_dataset", type=str, default=None)
    parser.add_argument("--hf-split", dest="hf_split", type=str, default=None)
    parser.add_argument("--confident-dataset", dest="confident_dataset", type=str, default=None)

    args = parser.parse_args(argv)

    tasks = {t.strip() for t in (args.tasks or "").split(",") if t.strip()}
    if not tasks:
        print("No tasks selected.")
        return 2

    # Apply runtime env knobs used by tests
    if args.items is not None:
        os.environ.setdefault("DEEPEVAL_CONTEXT_ITEMS", str(args.items))
        os.environ.setdefault("DEEPEVAL_JUDGE_ITEMS", str(args.items))
    if args.checkpoints:
        os.environ.setdefault("DEEPEVAL_CONTEXT_CHECKPOINTS", args.checkpoints)

    # Dataset validation: require at least one source for the selected tasks
    any_global = bool(args.json_file or args.hf_dataset or args.confident_dataset)
    # Per-task overrides present?
    has_ctx = bool(args.json_file_context)
    has_sum = bool(args.json_file_summary)
    has_graph = bool(args.json_file_graph)

    if not any_global and not has_ctx and not has_sum and not has_graph:
        print("ERROR: Provide dataset via --json-file or --huggingface-dataset or --confident-dataset (or per-task --json-file-<task>).")
        return 2

    # Propagate dataset configuration to tests via env vars
    if args.json_file:
        os.environ["EVAL_DATA_FILE"] = args.json_file
    if args.hf_dataset:
        os.environ["EVAL_HF_DATASET"] = args.hf_dataset
    if args.hf_split:
        os.environ["EVAL_HF_SPLIT"] = args.hf_split
    if args.confident_dataset:
        os.environ["EVAL_CONFIDENT_DATASET"] = args.confident_dataset

    # Task-specific overrides take precedence over global file
    if args.json_file_context:
        os.environ["EVAL_FILE_CONTEXT"] = args.json_file_context
    if args.json_file_summary:
        os.environ["EVAL_FILE_SUMMARY"] = args.json_file_summary
    if args.json_file_graph:
        os.environ["EVAL_FILE_GRAPH"] = args.json_file_graph

    test_paths = _resolve_deepeval_tests(tasks)
    if not test_paths:
        print("No DeepEval tests resolved for the selected tasks.")
        return 2

    # Ensure repo root on sys.path
    root = _project_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    try:
        import pytest
    except Exception as exc:
        print(f"pytest is required: {exc}")
        return 2

    # Ensure history dir exists for HTML outputs
    history_dir = _project_root() / "services" / "evaluations" / "history"
    try:
        history_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    pytest_args: List[str] = []
    pytest_args.extend(test_paths)
    pytest_args.extend(["-m", "llm_judge"])  # only DeepEval-marked tests
    pytest_args.extend(["-o", "markers=llm_judge: DeepEval LLM-as-judge tests only"])  # avoid warnings
    # If user didn't request HTML report, prefer console visibility
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_out = None
    if args.report:
        try:
            __import__("pytest_html")
            base = Path(args.report).stem
            html_out = str(history_dir / f"{base}_{ts}.html")
            pytest_args.append(f"--html={html_out}")
            pytest_args.append("--self-contained-html")
            pytest_args.append("--capture=tee-sys")  # include stdout in HTML
        except Exception:
            print("pytest-html not installed; skipping HTML report")
            pytest_args.append("-s")
    else:
        pytest_args.append("-s")
    pytest_args.append("-v" if args.verbose else "-q")

    if args.json_report:
        try:
            __import__("pytest_jsonreport")
            pytest_args.append("--json-report")
            pytest_args.append(f"--json-report-file={args.json_report}")
        except Exception:
            print("pytest-json-report not installed; skipping JSON report")

    print("Running DeepEval tests:", " ".join(pytest_args))
    if html_out:
        print(f"HTML report: {html_out}")
    return int(pytest.main(pytest_args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())



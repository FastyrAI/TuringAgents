from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Set


def _project_root() -> Path:
    # services/evaluations/cli.py -> up 2 to repo root
    return Path(__file__).resolve().parents[2]


def _resolve_test_paths(tasks: Set[str]) -> List[str]:
    root = _project_root()
    eval_tests = root / "services" / "evaluations" / "tests"

    summary_deepeval = eval_tests / "test_summarization.py"
    context_file = eval_tests / "test_context_compression.py"

    selected: List[str] = []

    if "summary" in tasks:
        selected.append(str(summary_deepeval))

    if "context-compression" in tasks:
        # Runs progressive and e2e DeepEval tests
        selected.append(str(context_file))
    elif "graph" in tasks:
        # Only the e2e graph QA pipeline
        selected.append(f"{context_file}::test_context_engineering_end_to_end_pipeline_deepeval")

    # Deduplicate while preserving order
    seen = set()
    unique_selected = []
    for s in selected:
        if s not in seen:
            seen.add(s)
            unique_selected.append(s)
    return unique_selected


def _plugin_available(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except Exception:
        return False


def _build_pytest_args(
    tests: List[str],
    html_report: str | None,
    json_report: str | None,
    verbose: bool,
) -> List[str]:
    args: List[str] = []
    args.extend(tests)

    # Restrict to DeepEval-marked tests by default
    args.extend(["-m", "llm_judge"])
    # Register marker to avoid warnings if pytest.ini missing in this package
    args.extend(["-o", "markers=llm_judge: tests that call external LLM-as-judge via DeepEval"])

    if verbose:
        args.append("-v")
    else:
        args.append("-q")

    if html_report and _plugin_available("pytest_html"):
        args.append(f"--html={html_report}")
        args.append("--self-contained-html")
        # capture both to console and report so details/checkbox work
        args.append("--capture=tee-sys")

    if json_report and _plugin_available("pytest_jsonreport"):
        args.append("--json-report")
        args.append(f"--json-report-file={json_report}")

    # If no HTML report, prefer live console output
    if not html_report:
        args.append("-s")
    return args


def _set_env_overrides(items: int | None, checkpoints: str | None, budget_usd: float | None, p95_ms: int | None) -> None:
    if items is not None:
        # Apply to both suites that support item limiting
        os.environ.setdefault("DEEPEVAL_CONTEXT_ITEMS", str(items))
        os.environ.setdefault("DEEPEVAL_JUDGE_ITEMS", str(items))

    if checkpoints:
        os.environ.setdefault("DEEPEVAL_CONTEXT_CHECKPOINTS", checkpoints)

    if budget_usd is not None:
        os.environ.setdefault("DEEPEVAL_BUDGET_USD", str(budget_usd))

    if p95_ms is not None:
        os.environ.setdefault("DEEPEVAL_P95_MS", str(p95_ms))


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ta-eval",
        description="Run DeepEval-based evaluations using existing tests",
    )
    parser.add_argument(
        "--tasks",
        type=str,
        default="context-compression,summary",
        help="Comma-separated: context-compression,summary,graph",
    )
    parser.add_argument("--items", type=int, default=None, help="Cap dataset size")
    parser.add_argument(
        "--checkpoints",
        type=str,
        default=None,
        help="Progressive context checkpoints, e.g. '2,3,5'",
    )
    parser.add_argument("--budget-usd", type=float, default=None, help="Budget guard (informational)")
    parser.add_argument("--p95-ms", type=int, default=None, help="Latency guard (informational)")
    parser.add_argument("--report", type=str, default=None, help="HTML report path (requires pytest-html)")
    parser.add_argument("--json-report", type=str, default=None, help="JSON report path (requires pytest-json-report)")
    parser.add_argument("--verbose", action="store_true", help="Verbose pytest output")

    # Placeholder dataset flags for future sources; accepted but unused per ADR MVP
    parser.add_argument("--file", type=str, default=None, help="Dataset file (unused; tests use built-in datasets)")
    parser.add_argument("--huggingface-dataset", type=str, default=None, help="HF dataset (unused)")
    parser.add_argument("--hf-split", type=str, default=None, help="HF split (unused)")
    parser.add_argument("--confident-dataset", type=str, default=None, help="ConfidentAI dataset id (unused)")
    parser.add_argument("--file-context", type=str, default=None, help="Per-task dataset override (unused)")
    parser.add_argument("--file-summary", type=str, default=None, help="Per-task dataset override (unused)")
    parser.add_argument("--file-graph", type=str, default=None, help="Per-task dataset override (unused)")

    args = parser.parse_args(argv)

    tasks = {t.strip() for t in (args.tasks or "").split(",") if t.strip()}
    if not tasks:
        print("No tasks selected; nothing to run.")
        return 2

    tests = _resolve_test_paths(tasks)
    if not tests:
        print("No tests resolved for the selected tasks.")
        return 2

    _set_env_overrides(args.items, args.checkpoints, args.budget_usd, args.p95_ms)

    # Prepare history output for HTML report
    history_dir = root / "services" / "evaluations" / "history"
    try:
        history_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = Path(args.report).stem if args.report else "results"
    html_out = str(history_dir / f"{base_name}_{ts}.html") if _plugin_available("pytest_html") else None

    pytest_args = _build_pytest_args(
        tests=tests,
        html_report=html_out,
        json_report=args.json_report,
        verbose=args.verbose,
    )

    # Ensure repo root is on sys.path so tests can import local packages
    root = _project_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    try:
        import pytest  # noqa: WPS433 (runtime import intentional)
    except Exception as exc:  # pragma: no cover
        print(f"pytest is required to run evaluations: {exc}")
        return 2

    print("Running DeepEval tests with args:", " ".join(pytest_args))
    if html_out:
        print(f"HTML report: {html_out}")
    code = pytest.main(pytest_args)
    return int(code)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())



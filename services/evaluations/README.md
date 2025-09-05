## Evaluations (DeepEval)

This package runs DeepEval-based evaluation tests for the Context Engineering service and summarization.

What it does:
- Runs only DeepEval-marked tests (LLM-as-a-judge) that live in `services/evaluations/tests`.
- Uses your real judge model (Gemini/OpenAI/Anthropic) via environment variables.
- Accepts external datasets (JSON/JSONL) for each task.
- Produces optional HTML/JSON reports if pytest plugins are installed.

Prerequisites:
- Install packages (from repo root):
  ```bash
  uv sync
  ```
- Set a judge API key (pick one):
  ```bash
  export GEMINI_API_KEY=...        # or OPENAI_API_KEY / ANTHROPIC_API_KEY
  ```

Judge selection (optional):
```bash
export EVAL_JUDGE_PROVIDER=gemini   # or openai / anthropic
export EVAL_JUDGE_MODEL=gemini-1.5-pro
```

How to run (single command):
```bash
python3 -m services.evaluations.evaluation_runner \
--tasks summary,context-compression \
  --json-file datasets/context_compression_dataset.json \
  --items 2
```

Flag Explanations:

`--tasks` → Which evaluation to run:
- `summary` → Tests summarization algorithms (stuff, refine, map_reduce, recursive, hybrid_map_refine, extractive, ensemble)
- `context-compression` → Tests context compression with progressive context testing and end-to-end pipeline
- `graph` → Tests only the end-to-end graph QA pipeline
- Multiple tasks: `--tasks summary,context-compression`

`--json-file <file>` → Path to dataset file (JSON/JSONL). Applies to all tasks unless overridden.
Examples:
- `--json-file datasets/context_compression_dataset.json`
- `--json-file datasets/test_summary.json`

Dataset Override Flags:

`--json-file-context-compression` → Dataset specifically for context compression tasks
Example: `--json-file-context-compression datasets/context_compression_dataset.json`

`--json-file-summary` → Dataset specifically for summarization tasks  
Example: `--json-file-summary datasets/test_summary.json`

`--json-file-graph` → Dataset specifically for graph QA tasks
Example: `--json-file-graph datasets/context_compression_dataset.json`

Control Flags:

`--items <N>` → Limits dataset items processed (cost control)
Example: `--items 5` processes only first 5 items

`--checkpoints "<list>"` → Progressive context sizes for context compression
Example: `--checkpoints "2,3,5"` tests with 2, 3, and 5 context items

`--verbose` → Detailed output during evaluation

`--json-report <file>` → Generates JSON report for programmatic analysis
Example: `--json-report results.json`

`--budget-usd <float>` → Budget guard (informational)
Example: `--budget-usd 10.0`

`--p95-ms <int>` → Sets a latency guard (informational alerts)  
Example: `--p95-ms 5000`

Datasets (required):
- Provide one of:
  - `--json-file datasets/context_compression_dataset.json` (global for all tasks)
  - Per-task overrides using the flags above
- Supported formats:
  - JSON: list of objects
  - JSONL: one JSON object per line

Expected schemas:
- Summary:
  ```json
  { "input": "...", "context": "..." }
  ```
- Context-Compression / Graph QA:
  ```json
  { "question": "...", "context": "...", "expected_output": "..." }
  ```

Results:

Evaluation results are stored in `.deepeval/.deepeval-history.json` with comprehensive metrics and scoring data.

Example Commands:

Basic summarization test:
```bash
python3 -m services.evaluations.evaluation_runner \
  --tasks summary \
  --json-file datasets/test_summary.json \
  --items 2
```

Context compression with custom checkpoints:
```bash
python3 -m services.evaluations.evaluation_runner \
  --tasks context-compression \
  --json-file datasets/context_compression_dataset.json \
  --checkpoints "2,5,10" \
  --items 3
```

Multi-task evaluation:
```bash
python3 -m services.evaluations.evaluation_runner \
  --tasks summary,context-compression \
  --json-file-summary datasets/test_summary.json \
  --json-file-context-compression datasets/context_compression_dataset.json \
  --items 2 \
  --verbose
```

Task mapping:
- `--tasks summary` → `tests/test_summarization.py`
- `--tasks context-compression` → `tests/test_context_compression.py` (progressive and E2E)

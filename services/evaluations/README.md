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
- python3 -m services.evaluations.evaluation_runner --tasks summary|context-compression  --json-file <file> --report results
  ```

Datasets (required):
- Provide one of:
  - `--json-file /path/to.json` (global for all tasks)
  - Per-task overrides:
    - `--json-file-context-compression` for context-compression
    - `--json-file-summary` for summarization
- Supported formats:
  - JSON: list of objects or `{ "data": [ ... ] }`
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

Task mapping:
- `--tasks summary` → `tests/test_summarization.py`
- `--tasks context-compression` → `tests/test_context_compression.py` (progressive and E2E)

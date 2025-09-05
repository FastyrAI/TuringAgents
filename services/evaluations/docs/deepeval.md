# Evaluation Pipeline – Architecture Decision Record (ADR)

**Project:** AI Agent OS Framework
**Component:** Evaluation Pipeline (DeepEval-based)
**Date Created:** September 4, 2025
**Status:** Approved – Initial Implementation

---

## 0. Scope & Objectives

Deliver a **production-grade evaluation pipeline** that:

* Executes end-to-end tests for **Context-Compression, Summarization, and Graph QA**.
* Uses **DeepEval** with real LLM-as-a-judge scoring (no mocking except optional GraphDB).
* Supports multiple dataset sources: local files, Hugging Face datasets, ConfidentAI dataset store.
* Runs from a **single Python command** with task flags (`--tasks context-compression,summary,graph`).
* Produces **deterministic, reproducible, threshold-based results** suitable for CI/CD gating.
* Provides **consolidated reports** (console, JSON, HTML) with per-case outcomes and summaries.

---

## 1. Core Decisions

### 1.1 Execution Framework

* **Tooling:** Pytest + DeepEval.
* **Judge Model:** Constructed once per test run (**session scope**).
* **Judge Selection:** Via service factory > environment (`EVAL_JUDGE_PROVIDER`, `EVAL_JUDGE_MODEL`) > auto-detect keys (Gemini, OpenAI, Anthropic).
* **Caching:** Content-hash based cache for judge calls to reduce cost and ensure stability.

### 1.2 Task Modularity

* **Evaluation Task Interface:** Common interface for `ContextCompressionEval`, `SummaryEval`, `GraphEval`.
* **Responsibilities:**

  * Load dataset
  * Format inputs/outputs
  * Call system under test (router, summarizer, graph)
  * Package test case for DeepEval
* **Extensibility:** New tasks can be added by implementing the interface without altering core pipeline.

### 1.3 Dataset Handling

* **Sources:**

  * `--file <path.jsonl>`
  * `--huggingface-dataset <repo>` (+ optional `--hf-split`)
  * `--confident-dataset <id>`
* **Per-task Overrides:** `--file-context`, `--file-summary`, `--file-graph`.
* **Normalization:** All datasets converted to a common schema before evaluation.
* **Validation:** Fail-fast if required fields are missing.

### 1.4 Error Handling

* **Retries:** Exponential backoff for transient errors.
* **Graceful Degradation:** Skip failing cases, log error, continue rest of suite.
* **GraphDB Mocking:** Deterministic responses, enabled via `EVAL_GRAPH_BACKEND=mock`.

### 1.5 Thresholds & Pass/Fail

* **Per-Metric Thresholds:** Configurable via environment (`DEEPEVAL_FAITHFULNESS_THRESHOLD`, `DEEPEVAL_RELEVANCY_THRESHOLD`, etc.).
* **Default Metrics:**

  Check the exisintg directory of context engieering and use test cases from there only for now, if you find you can update the matirces from there just do that, but testcases should be just like it was there
* **Case Result:** Pass only if all metric scores ≥ thresholds.
* **Run Result:** Fail if any case fails (CI/CD gate).

### 1.6 Reporting & Observability

* **Outputs:**

  * Console logs with progress + summary
  * JSON report (machine-readable)
  * HTML report (human-readable)
* **Logs:**

  * Input ID, task, actual output, scores, verdicts
  * Error messages for failed/skipped cases
* **Integration:** Exit code reflects success/failure for CI pipelines.

### 1.7 Reproducibility

* **Judge Settings:** Deterministic (temperature=0).
* **Cache:** Reuse identical judge evaluations across runs.
* **Randomness:** Any pseudo-random steps seeded.
* **Mocking:** GraphDB mock ensures stable graph outputs.

---

## 2. CLI & Command Contract

**Flags:**

* `--tasks context-compression,summary,graph`
* `--file <path.jsonl>` OR `--huggingface-dataset <repo>` OR `--confident-dataset <id>`
* Per-task dataset overrides: `--file-context`, `--file-summary`, `--file-graph`
* `--items <N>` → cap dataset size
* `--checkpoints "2,3,5"` → progressive context test checkpoints
* `--budget-usd <float>`, `--p95-ms <int>` → resource guards
* `--report out.html`, `--json-report out.json`
* `--verbose`

## 3. Security & Governance

* **API Keys:** Managed via environment variables; never hard-coded.
* **Isolation:** No mocking of LLM judge; only GraphDB allowed to mock.
* **PII:** Redacted or sanitized in reports where necessary.

---

## 4. Acceptance Criteria (MVP)

* Runs with **single command** across tasks.
* Evaluates real model outputs with DeepEval judge.
* Enforces per-metric thresholds.
* Generates structured JSON + HTML reports.
* Supports deterministic GraphDB mocking.
* Deterministic outputs under repeated runs.

---

## 5. Risks & Mitigations

* **LLM nondeterminism →** Use temperature=0, caching .
* **High cost from judge calls →** Cache + item limits (`--items`) .
* **Graph dependency unstable →** Mock option with deterministic responses.
* **Threshold drift →** Allow thresholds to be configured per environment.

---

## 6. Consequences

* **Positive:** Stable, extensible, CI-friendly evaluation framework.
* **Trade-offs:** Added complexity (caching, config management). Slightly more setup overhead for environment variables.

---

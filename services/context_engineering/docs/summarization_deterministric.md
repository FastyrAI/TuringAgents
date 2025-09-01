Summarization Evaluation – Architecture Decision Record (ADR)

Project: AI Agent OS Framework
Component: Summarization Evaluation (Deterministic Metrics)
Date Created: August 28, 2025
Status: Draft

0. Scope & Objectives

Deliver a reproducible, on-demand evaluation subsystem for summarization algorithms that:

Pulls golden datasets directly from Confident AI (cloned and version-controlled there).

Supports deterministic metrics only (ROUGE, METEOR, BERTScore).

Enables comparisons across algorithms (Stuff, Refine, MapReduce, Recursive, Hybrid Map-Refine, Extractive, Ensemble).

Provides baseline tracking for regression detection.

Operates in ad-hoc mode (triggered manually when needed, not daily).

Ensures low cost, high reproducibility, and stable reporting.

1. Core Decisions
1.1 Dataset Integration (Confident AI)

Source of Truth: All golden datasets (SQuAD slice + domain-specific docs) are hosted on Confident AI.

Fetch Model: Evaluator fetches datasets dynamically from Confident AI APIs when tests are triggered.

User-Provided Inputs:

Dataset name or ID in Confident AI.

Run configuration (algorithm list, max samples, etc.).

Versioning: Confident AI ensures dataset version control. Runs always log the dataset version hash to guarantee reproducibility.

1.2 Evaluation Metrics

Deterministic set (always included):

ROUGE-1 / ROUGE-2 / ROUGE-L → content coverage + fluency.

METEOR → paraphrasing & synonym tolerance.

BERTScore (F1) → semantic fidelity.

1.3 Assertions & Thresholds

ROUGE-L F1 drop ≤ 1.0 point compared to baseline.

METEOR drop ≤ 0.01 compared to baseline.

BERTScore F1 ≥ 0.85; drop ≤ 0.005 from baseline.

Failures flagged for manual review.

1.4 Execution Model

On-demand execution, triggered manually with required Confident AI dataset info.

Workflow:

Pull dataset from Confident AI.

Run selected summarization algorithms.

Compute metrics (ROUGE, METEOR, BERTScore).

Store artifacts (summaries + metrics).

Outputs:

Metrics reports (CSV/HTML).

Per-item summaries (JSON artifacts).

Comparison vs last stable run.

2. Security & Governance

Confident AI provides dataset storage and version control.

Reports and artifacts are archived locally or in CI/CD with timestamps.

Access controlled via Confident AI authentication keys.

3. Provenance & Baseline Tracking

Each run logs:

Algorithm, model ID, prompt version.

Confident AI dataset name + version hash.

Metrics and artifacts.

Ensures exact reproducibility of evaluations.

4. Evaluation & QA

Automated metrics: ROUGE, METEOR, BERTScore.

Baseline validation: Compare against previous Confident AI dataset runs.

Artifacts for manual QA: Generated summaries stored alongside metrics.

5. Performance & Cost

Deterministic metrics → lightweight, local compute only.

Confident AI handles dataset management → no local dataset overhead.

Evaluation triggered only when required → cost-efficient.

6. Tests Surface (Internal)

evaluate(dataset_id, algorithm) → fetches dataset from Confident AI, runs metrics.

compare(run_id_a, run_id_b) → highlights metric deltas.

report(run_id) → exports CSV/HTML.

7. Monitoring & Observability

No continuous monitoring — ad-hoc reporting only.

Optionally integrate into CI/CD → attach reports to build artifacts.

8. Human-in-the-Loop

Manual review required if thresholds are breached.

Annotators may use Confident AI dataset annotations for deeper QA.

9. Acceptance Criteria

Metrics reproducibly computed on Confident AI datasets.

ROUGE/METEOR/BERTScore supported.

Reports + artifacts generated and stored.

Baseline comparison functional.

10. Risks & Mitigations

Confident AI downtime → fallback to cached dataset snapshot.

Dataset drift → mitigate via Confident AI version hashes.

Metric blind spots → may miss factual errors → QA-based eval added later.

11. Decision Log

Golden datasets hosted on Confident AI.

Chosen deterministic metrics (ROUGE, METEOR, BERTScore).

On-demand execution only (not daily).

Dataset versioning + provenance tied to Confident AI IDs.
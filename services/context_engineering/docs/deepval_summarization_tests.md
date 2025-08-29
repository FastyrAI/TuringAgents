LLM-as-Judge Summarization Evaluation (DeepEval + Confident AI)
Purpose
 Run periodic, on-demand quality checks for summarization using DeepEval’s built-in metrics (LLM-as-judge) on golden data pulled from Confident AI. This complements deterministic metrics and is used only before releases or after major changes.
1) What we evaluate
Faithfulness — summary is supported by the source context (no unsupported claims).
Answer Relevancy — summary directly addresses the input prompt/task.
Hallucination — penalizes fabricated content not present in context.
(Optional later: Coherence, Fluency, Conciseness via DeepEval or G-Eval style prompts.)
2) Data source (Confident AI)
Source of truth: Golden datasets live in Confident AI.
Access method: Pull a dataset by alias or dataset ID (e.g., test-data-set) at run time.
Versioning: Always record the dataset version/hash returned by Confident AI for reproducibility.
Required fields per record:
input — the summarization instruction or user prompt.
context — the full source text to which the summary must be faithful.
expected_output — the gold/reference summary (optional for some metrics, recommended for audit).
Optional fields:
Domain tag, length bucket, document ID, algorithm tag, any must-include facts for manual review.
3) Evaluation flow (high level)
Identify dataset alias/ID in Confident AI (e.g., test-data-set).
Fetch a run slice:
Smoke: 3–10 items (plumbing check).
Pre-release: 50–100 items (recommended).
Full audit: full set (rare; expensive).
Generate summaries with each algorithm you want to judge (Stuff, Refine, MapReduce, Recursive, Hybrid, Extractive, Ensemble).
Keep the model ID/version and prompt version fixed for the run.
Pass into DeepEval with selected metrics:
Faithfulness, Answer Relevancy, Hallucination (as your standard set).
Collect outputs:
Per-item metric scores + judge comments.
Run-level aggregates (mean/median, fail rates).
Archive & compare:
Save reports and raw judgments.
Compare against last accepted run (baseline).
4) Pass/fail criteria (suggested starting point)
Faithfulness: any item score < 0.70 → flag for manual review.
Answer Relevancy: run average ≥ 0.70; > 5% items below 0.70 → review.
Hallucination: ≤ 5% items flagged/unacceptable by your chosen scale.
Composite (if used 1–5): average ≥ 4.0 across the sample.
Release gate: prioritize Faithfulness over stylistic dimensions.
Calibrate these thresholds once against a small pilot and human judgments, then fix them for future runs.
5) Determinism & cost controls
Judge LLM settings: temperature 0, top-p 1, fixed model/version.
Caching: enable DeepEval result caching so repeated evaluations don’t rebill.
Slice sizes: cap at ≤100 items per pre-release run to keep cost predictable.
Pin data: always log Confident AI dataset alias + version hash in artifacts.
6) Artifacts to save per run
Provenance: dataset alias + version/hash, judge model ID/version, summarizer model IDs, prompt versions, timestamp, git SHA.
Per-item record: input, context hash (not the full context if sensitive), produced summary, metric scores, judge comments.
Aggregate report: averages, medians, % fails per metric, breakdown by algorithm and by slice (length/domain).
7) Operational checklist
Before running
You have the Confident AI dataset alias/ID and access credentials.
The dataset records include input, context, and ideally expected_output.
Judge model/version and thresholds are agreed and documented.
During run
Pull the dataset by alias.
Limit to the intended sample size (smoke/pre-release/full).
Generate summaries with the selected algorithms.
Evaluate with DeepEval metrics (Faithfulness, Answer Relevancy, Hallucination).
Store per-item and aggregate outputs.
After run
Compare against last baseline.
Triage any Faithfulness < 0.70 or Hallucination flags.
Record decisions (accept, rollback, tune prompts/algorithms).
8) Common pitfalls & guardrails
Passing the gold reference as “actual summary”: acceptable for pipeline smoke tests only. For real judging, evaluate the algorithm’s produced summary.
Weak or missing context: Faithfulness/Hallucination depend on the full source—ensure context is complete and de-redacted as appropriate.
Judge bias toward fluency: Do not over-weight fluency; keep Faithfulness primary in gating decisions.
Dataset drift: Never compare runs across different dataset versions—always pin to the Confident AI version/hash.
Inconsistent models: Changing judge or summarizer model versions without noting them invalidates comparisons.
9) Roles & responsibilities
Owner (Context Engineering): runs evaluation, maintains thresholds, curates golden data.
Model Ops: manages judge model/version pinning and caching configuration.
QA/HIL reviewers: inspect low-faithfulness or hallucination cases and sign off go/no-go.
10) Acceptance criteria
Confident AI dataset successfully pulled and logged with version/hash.
DeepEval metrics executed on the produced summaries for the chosen algorithms.
Reports and raw judgments archived with full provenance.
Any threshold breaches reviewed and dispositioned before release.
11) When to run
Before product releases affecting summarization.
After major changes to summarization algorithms, routing, prompts, or base LLMs.
On request when quality concerns are raised.
12) Future extensions (optional)
Add Coherence/Fluency/Conciseness judging (DeepEval or G-Eval rubric).
Add slice-aware reporting (by domain, length, algorithm) for deeper insights.
Combine with QA-based retention on the same Confident AI dataset for factual coverage checks.
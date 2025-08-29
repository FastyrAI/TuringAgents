# Context Engineering – Architecture Decision Record (ADR)

**Project:** AI Agent OS Framework
**Component:** Context Management (Graph Memory + Summarization Utility + Multi-LLM Router)
**Date Created:** August 27, 2025
**Status:** In Progress

---

## 0. Scope & Objectives

Deliver a **production-ready context engineering subsystem** that:

* Stores and manages all context externally in a **Neo4j knowledge graph**.
* Provides **flexible retrieval** (graph, vector, symbolic) with fusion ranking.
* Supports **multiple summarization strategies** (Stuff, Refine, MapReduce, Recursive, Hybrid Map-Refine, Extractive, Ensemble, Streaming).
* Routes across **GPT, Claude, Gemini, and OSS LLMs** with fallback and cost-aware selection.
* Ensures **faithfulness, traceability, and compliance** via must-include coverage, citations, lineage, and PII redaction.
* Operates in **real-time**, integrates with the global message queue, and supports multi-tenant governance.

---

## 1. Core Decisions

### 1.1 Graph Storage (Neo4j)

* **Nodes:** `Message`, `Entity`, `Fact`, `Summary`.
* **Edges:** `MENTIONS`, `REFERS_TO`, `NEXT`, `SUMMARIZES`.
* **Metadata:** scope (Session/Goal/Global), timestamp, embedding, version, created\_by.

### 1.2 Scoping Levels

* **Session-local:** ephemeral, expires after session.
* **Goal-local:** persists across a workflow until goal completion.
* **Global:** permanent organizational knowledge.

### 1.3 Retrieval Strategy

* **Hybrid:** Vector similarity + Graph traversal + Symbolic filters.
* **Fusion ranking:** Reciprocal Rank Fusion (RRF) + MMR diversity + coverage bonus + temporal decay.
* **Community quotas:** prevent single-topic bias.

### 1.4 Summarization Strategy

* **Faithfulness rules:** must-include coverage ≥95%, numeric/date guardrails, \[S#] citations.
* **Structured output:** Executive Summary → Key Points → Decisions/Next Steps.

**Supported algorithms:**

1. **Stuff Summarization** – single-pass LLM call; short contexts.
2. **Refine Summarization** – sequential chunking with iterative refinement.
3. **MapReduce Summarization** – parallel per-chunk summaries + reduce step.
4. **Recursive Summarization** – multi-level map-reduce for very large corpora.
5. **Hybrid Map-Refine** – map-reduce + final refine pass for polished quality.
6. **Extractive** – TextRank, BM25+MMR; zero LLM dependency.
7. **Ensemble** – multiple LLMs in parallel, merge with verification.
8. **Streaming** – sliding-window digests with periodic compaction.

### 1.5 Multi-LLM Router

* **Criteria:** context size, SLA (P0–P3), cost sensitivity, provider health, feature requirements (streaming/JSON/long-context).
* **Providers:** GPT (OpenAI), Claude (Anthropic), Gemini (Google), OSS (Llama/Qwen/Mixtral via vLLM/Ollama).
* **Fallback chain:** provider fail → next best → extractive-only.

### 1.6 Temporal Decay & Expiry

* Raw ephemeral messages auto-expire after TTL.
* Compaction into `:Summary` nodes.
* Decay score used in retrieval weighting.

### 1.7 Conflict Resolution

* Graph branching for concurrent/contradictory updates.
* LLM-assisted merge with explainable diffs.
* Conflict log stored in Postgres for audits.

---

## 2. Security & Governance

* **Multi-tenancy:** Org-level isolation; RBAC on nodes/edges.
* **Field-level redaction:** PII hidden at retrieval.
* **Encryption:** At rest (Neo4j + audit DB) and in transit (TLS).
* **Schema governance:** Versioned schema, validation rules (no orphan edges, only valid relation types).
* **Compliance:** GDPR/CCPA deletion flows, regional provider routing.

---

## 3. Data Lineage & Provenance

* Every context mutation logged: input → nodes → retrieval set → summary sentences \[S#] → output.
* Immutable audit log in Postgres JSONB with cryptographic hash + timestamp.

---

## 4. Evaluation & QA

* **Golden datasets:** chat logs, transcripts, long-form docs, multi-doc sets.
* **Automated tests:** recall %, numeric/date accuracy, latency SLA compliance.
* **Dashboards:** must-include coverage, provider latency, error rates.

---

## 5. Disaster Recovery & Resilience

* Daily full + hourly incremental backups (Neo4j + audit DB).
* RabbitMQ DLQ replay for recovery.
* Chaos tests: simulate provider outages and queue overloads.
* Targets: RPO ≤ 15 min, RTO ≤ 1 h.

---

## 6. Performance & Cost Controls

* **Token budgeter:** allocate per SLA tier.
* **OSS fallback:** for bulk jobs.
* **Cache summaries:** reuse stable digests.
* **Benchmarks:**

  * Retrieval latency <150ms
  * LLM response within SLA
  * Graph traversal (10k nodes) <1s

---

## 7. API Surface

* `ingest(input, scope)`
* `retrieve(query, scope)`
* `summarize(nodes, algorithm)`
* `snapshot(session_id)`
* `verify(summary_id)`
* `explain(summary_id)`
* `resolve_conflict(node_a, node_b)`

**Features:**

* Idempotency keys.
* Rate limits per org.
* JSON + gRPC APIs.

---

## 8. Monitoring & Observability

* **Metrics:** recall %, mismatch %, provider chosen, graph growth, conflict rate.
* **Tracing:** distributed IDs across full pipeline.
* **Dashboards:** SLA heatmaps, token usage, cost reports.
* **Alerts:** SLA breaches, conflict spikes, abnormal graph growth.

---

## 9. Human-in-the-Loop

* Review workflows for high-stakes outputs.
* Annotator feedback loop stored in graph.
* Validation against must-include lists.

---

## 10. Integration with Global Message Queue

* All ops (ingest, retrieve, summarize) run via RabbitMQ.
* Retry policies with exponential backoff.
* Org-level FIFO ordering.
* DLQ for failed ops with replay capability.

---

## 11. Acceptance Criteria (MVP)

* End-to-end context pipeline operational (Neo4j + summarization + router).
* Support for all summarization strategies (Stuff, Refine, MapReduce, Recursive, Hybrid Map-Refine, Extractive, Streaming, Ensemble).
* Faithfulness checks (≥95% must-include recall, ≤1% numeric mismatch).
* Real-time streaming digests working.
* Multi-tenant access control enforced.
* Audit trail + provenance complete.

---

## 12. Risks & Mitigations

* **Provider outages →** multi-LLM fallback + extractive degrade.
* **Graph bloat →** expiry + compaction policies.
* **Conflicts →** branching + LLM-assisted merge.
* **Latency →** extractive-only P0 path.
* **Cost overruns →** OSS fallback + token budgeter.

---

## 13. Decision Log

* Neo4j selected as graph memory.
* RabbitMQ for queueing and retries.
* Adopt multi-scope (Session/Goal/Global).
* Implement hybrid/hierarchical summarization with verification.
* Router across GPT/Claude/Gemini/OSS.
* Add lineage, schema governance, expiry, and human-in-the-loop workflows.
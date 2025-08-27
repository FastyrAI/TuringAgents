## Global Message Queue — Implementation Plan

### Scope and principles
- **Scope**: Deliver the Message Queue MVP and near‑term features described in the ADR.
- **Concurrency principle**: Queue is concurrency‑agnostic. Agents enforce any serialization/ordering they require. No queue‑level per‑agent FIFO/locking.

### Milestone 1 — Core reliability and UX
- Step 1.1 — **Response types**: Implement `stream_chunk`, `stream_complete`, `progress`, `acknowledgment` end‑to‑end (worker emit; coordinator forward; agent consume). Add metrics and tests.
- Step 1.2 — **Error policies + priority demotion**: Error→policy map (no‑retry / linear / exponential). Demote P0→P1→P2→P3 on each retry (bounded at P3). Metrics and tests.
- Step 1.3 — **DLQ retention + replay**: Configurable retention (e.g., 90 days) purge job for `dlq_messages`. Improve replay UX (`--dry-run`, filters, batch progress). Metrics/tests.
- Step 1.4 — **Audit coverage + batching**: Add `promoted`, `conflict_*` events. Batch `message_events` writes (100 events or 1s). Metrics/tests.
- Step 1.5 — **Worker concurrency**: Configurable concurrency/prefetch for org‑level parallelism; remove any per‑agent locking assumptions; document best‑effort ordering.
  - Implemented: Added `WORKER_PREFETCH` (AMQP QoS) and `WORKER_CONCURRENCY` (semaphore) to bound effective concurrency per worker; responses are routed per-message `agent_id` with fallback to worker default; ADR/README updated to emphasize best‑effort ordering.

### Milestone 2 — Throughput and backpressure
- Step 2.1 — **Time‑based promotion**: TTL/DLX chain or scheduler for P3→P2 (30s), P2→P1 (15s), P1→P0 (5s). Record `promoted` events.
- Step 2.2 — **Backpressure safeguards + alerts**: Producer throttling + emergency reject for non‑P0; Prometheus alert rules for depth tiers; optional per‑org caps and cooldowns.
- Step 2.3 — **Autoscaling polish**: Parameterize KEDA thresholds via config; env‑specific defaults; docs/runbooks.
- Step 2.4 — **Coordinator improvements**: Dynamic agent register/unregister; buffering/backpressure on per‑agent queues; drop policy for runaway agents.

### Milestone 3 — Platform features and governance
- Step 3.1 — **Schema versioning + migrations**: Version router with auto‑migration stubs; support current + previous major.
- Step 3.2 — **Conflict detection registry**: Shared registry (PostgreSQL/Redis) to detect resource conflicts; emit `conflict_*` events; deferral policy.
- Step 3.3 — **Resource limits + sandbox hooks**: Parse optional `resource_limits`; add handler timeouts; sandbox interface (stub) for future isolation (VM/containers).
- Step 3.4 — **Security boundaries**: Per‑tenant authz model (vhosts/creds strategy); at‑rest encryption policy; secret rotation runbooks.
- Step 3.5 — **Token allocation service**: Importance scoring (blocked deps + retries), tier borrowing, multi‑provider fallback, telemetry.

### Cross‑cutting deliverables
- **Metrics**: Streaming lifecycle, promotions/demotions, batching flushes, conflict detection, throttling/alerts.
- **Docs**: Keep ADR and runbooks up‑to‑date; operational guides for promotion/backpressure/alerts.
- **Tests**: Unit (policies, promotion, demotion); integration (streaming, coordinator); load tests.

### Acceptance criteria (summarized)
- Streaming responses (chunks + completion) flow end‑to‑end; progress/ack visible.
- Retries follow error policies; priority demotes on each retry; metrics reflect transitions.
- Time‑based promotion moves aged messages up priorities; `promoted` events recorded.
- Backpressure thresholds trigger throttling/alerts; autoscaling acts predictably.
- Within an org, multiple agents run in parallel; ordering is agent‑managed where required.
- Versioning accepts current and previous major; auto‑migrations applied.
- Conflict detection and resource limits observable via metrics/audit.

### Notes
- This plan reflects the ADR update: agent‑managed serialization and best‑effort ordering at the queue layer.


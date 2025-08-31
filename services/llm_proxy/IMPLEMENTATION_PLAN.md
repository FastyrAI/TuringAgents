## LiteLLM Proxy Service — Implementation Plan

This plan adds a production-ready LiteLLM proxy as a service under `services/llm_proxy`, leveraging the official GHCR images and the deployment patterns summarized in `RESEARCH.md`.

### Objectives
- Provide an internal, OpenAI-compatible gateway for LLM requests via LiteLLM.
- Support multiple providers (Azure OpenAI, OpenAI, Bedrock, etc.) with usage-based routing, fallbacks, and Redis-backed coordination.
- Offer local dev via Docker Compose and production manifests for Kubernetes (HPA-based autoscaling).
- Enforce strong security posture (non-root, secrets management, virtual keys, TLS/mTLS-ready) and high observability (Prometheus/Datadog).

### Out of Scope (initial phase)
- Custom forking of LiteLLM. We will use the official images and configs.
- Building a bespoke admin UI or key management system beyond LiteLLM’s built-ins.

---

## Deliverables
- Configuration-driven LiteLLM service that runs locally and in Kubernetes.
- Base configuration file `litellm_config.yaml` with env-var integration.
- Docker Compose integration for local development.
- Kubernetes manifests (Deployment, Service, HPA, ConfigMap, Secret, optional NetworkPolicy/Ingress).
- Example `.env.example` and secret handling guidance.
- Basic smoke/load test scripts and CI hooks.
- Security hardening notes aligned with `RESEARCH.md`.

---

## Target Directory Layout

```
services/llm_proxy/
  IMPLEMENTATION_PLAN.md          # this document
  RESEARCH.md                     # prior research
  config/
    litellm_config.example.yaml   # example config w/ env placeholders
  k8s/
    deployment.yaml
    service.yaml
    hpa.yaml
    configmap.yaml
    secret.yaml                   # references external secret store in real envs
    networkpolicy.yaml            # optional, recommended
    ingress.yaml                  # optional, if ingress required
  compose/
    docker-compose.override.yml   # dev-only overlay for root compose
  scripts/
    smoke.sh
    load_test.sh
  README.md
```

Notes:
- We will reference the official image: `ghcr.io/berriai/litellm:main-stable` (or `litellm-non_root`/`litellm-database` variants as needed).
- Prefer single-worker configuration and separate health app per research findings.

---

## Configuration

LiteLLM supports a layered configuration model (env → YAML → API). We will use YAML with env placeholders as primary, checked into `config/litellm_config.example.yaml` and injected via ConfigMap/volumes for runtime.

Example `config/litellm_config.example.yaml`:
```yaml
model_list:
  - model_name: gpt-4o
    litellm_params:
      model: azure/${AZURE_DEPLOYMENT_NAME}
      api_base: ${AZURE_API_BASE}
      api_key: ${AZURE_API_KEY}
      rpm: 60
      tpm: 100000

general_settings:
  master_key: ${LITELLM_MASTER_KEY} # must start with 'sk-'
  database_url: ${DATABASE_URL}
  database_connection_pool_limit: 10
  proxy_batch_write_at: 60

router_settings:
  routing_strategy: usage-based-routing-v2
  redis_host: ${REDIS_HOST}
  redis_port: ${REDIS_PORT}
  redis_password: ${REDIS_PASSWORD}

features:
  separate_health_app: true
  pre_call_health_checks: true
```

Critical env vars (documented in `.env.example`):
- `LITELLM_MASTER_KEY` (format: `sk-...`)
- `DATABASE_URL` (PostgreSQL)
- `AZURE_API_BASE`, `AZURE_API_KEY`, `AZURE_DEPLOYMENT_NAME` (or provider equivalents)
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`
- `SEPARATE_HEALTH_APP=1` (if not enabled via YAML)

Security note: Do not check real secrets into version control. Use external secret stores (AWS/GCP Secret Manager, Vault, Kubernetes Secrets) in production.

---

## Local Development (Docker Compose)

We will extend the repository’s root `docker-compose.yml` via a dev-only overlay at `services/llm_proxy/compose/docker-compose.override.yml`.

Example overlay (dev):
```yaml
version: "3.9"
services:
  litellm:
    image: ghcr.io/berriai/litellm:main-stable
    ports:
      - "4000:4000"
    environment:
      DATABASE_URL: "postgresql://llmproxy:pass@db:5432/litellm"
      LITELLM_MASTER_KEY: "sk-dev-1234"
      REDIS_HOST: "redis"
      REDIS_PORT: "6379"
      SEPARATE_HEALTH_APP: "1"
    volumes:
      - ../../llm_proxy/config/litellm_config.example.yaml:/app/config.yaml:ro
    command: ["--config", "/app/config.yaml", "--detailed_debug"]
    depends_on:
      - db
      - redis

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: litellm
      POSTGRES_USER: llmproxy
      POSTGRES_PASSWORD: pass
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
```

Usage:
- Copy `config/litellm_config.example.yaml` to `config/litellm_config.yaml` and adjust env vars.
- Run: `docker compose -f docker-compose.yml -f services/llm_proxy/compose/docker-compose.override.yml up -d`.
- Health endpoints: `http://localhost:4000/health`, `http://localhost:4000/health/liveliness`, `.../readiness`.

---

## Kubernetes Manifests

We will provide production-ready manifests in `services/llm_proxy/k8s/`:

1) `configmap.yaml` (mount example config):
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: litellm-config
data:
  config.yaml: |
    # Paste sanitized example YAML here or mount from bucket in prod
```

2) `secret.yaml` (env-only stub; real secrets from external manager):
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: litellm-secrets
type: Opaque
stringData:
  LITELLM_MASTER_KEY: sk-change-me
  DATABASE_URL: postgresql://user:pass@db:5432/litellm
  REDIS_PASSWORD: ""
  AZURE_API_KEY: ""
  AZURE_API_BASE: ""
  AZURE_DEPLOYMENT_NAME: ""
```

3) `deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: litellm
spec:
  replicas: 2
  selector:
    matchLabels:
      app: litellm
  template:
    metadata:
      labels:
        app: litellm
    spec:
      containers:
        - name: litellm
          image: ghcr.io/berriai/litellm:main-stable
          ports:
            - containerPort: 4000
          envFrom:
            - secretRef:
                name: litellm-secrets
          env:
            - name: REDIS_HOST
              value: redis
            - name: REDIS_PORT
              value: "6379"
            - name: SEPARATE_HEALTH_APP
              value: "1"
          volumeMounts:
            - name: config
              mountPath: /app/config.yaml
              subPath: config.yaml
          args: ["--config", "/app/config.yaml"]
          resources:
            requests:
              cpu: "500m"
              memory: "1Gi"
            limits:
              cpu: "1000m"
              memory: "2Gi"
          readinessProbe:
            httpGet:
              path: /health/readiness
              port: 4000
            initialDelaySeconds: 30
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health/liveliness
              port: 4000
            initialDelaySeconds: 120
            periodSeconds: 15
      volumes:
        - name: config
          configMap:
            name: litellm-config
```

4) `service.yaml`:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: litellm
spec:
  selector:
    app: litellm
  ports:
    - name: http
      port: 80
      targetPort: 4000
  type: ClusterIP
```

5) `hpa.yaml`:
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: litellm
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: litellm
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

6) `networkpolicy.yaml` (optional, recommended): restrict ingress to cluster services and egress to providers/DB/Redis.

7) `ingress.yaml` (optional): configure TLS termination and routes if public exposure is required.

Cloud config source: Instead of ConfigMap mounts, production can fetch config from S3/GCS using `LITELLM_CONFIG_BUCKET_NAME` and `LITELLM_CONFIG_BUCKET_OBJECT_KEY` to enable dynamic updates.

---

## Security Hardening
- Prefer non-root image: `ghcr.io/berriai/litellm-non_root:main-stable` when feasible.
- Secrets in external managers; Kubernetes Secrets only as last-mile delivery (no plaintext in repo).
- `LITELLM_SALT_KEY` for credential encryption must be set before first use and kept stable.
- TLS/mTLS via service mesh or Ingress (cert-manager). Avoid plaintext credentials in logs.
- Virtual keys for fine-grained access control (limit models, budgets, rate limits per key).
- NetworkPolicies to restrict egress/ingress. Disable verbose logs in prod.

---

## Observability & Metrics
- Prometheus scraping via ServiceMonitor (if Prometheus Operator present) or annotations on `service.yaml`.
- Datadog integration for LLM observability (request/latency/usage). Enable structured JSON logging.
- Expose health endpoints on separate health app to avoid false restarts during traffic spikes.
- Batch DB writes (`proxy_batch_write_at: 60`), monitor queue time, error rates, cooldown events.

---

## Performance & Scaling
- Single Uvicorn worker per container (per research: multi-worker reduces throughput 20–30%).
- Redis for state/routing; specify host/port/password individually (avoid single `redis_url`).
- Configure connection pools: DB pool 10–20; Redis tuned for expected RPS.
- Usage-based routing with fallback chains; enable circuit breaker cooldowns (e.g., 30s after 3 failures).
- Cache via Redis (semantic matching) to reduce LLM calls for repeated prompts.

---

## Testing Strategy

Scripts in `services/llm_proxy/scripts/`:
- `smoke.sh`: Simple `/v1/chat/completions` request against the proxy with a mock/test model; verifies 200 and basic JSON shape.
- `load_test.sh`: k6 or vegeta-based RPS test with configurable concurrency; measure p50/p95 latency, error rates, 429s.

Recommended CI steps:
- Lint YAML and validate manifests (kubeval/kubeconform).
- Run smoke test against a Compose-up’d service.
- Optional: Run a short load test (1–2 mins) on PRs touching `services/llm_proxy/`.

Acceptance tests (examples):
- OpenAI compatibility: `/v1/chat/completions` works with a configured model, streams when requested, and returns usage.
- Fallback routing triggers when primary model is forced-fail (simulate 5xx/429) and recovers after cooldown.
- Health probes remain green during moderate load (separate health app validation).

---

## Rollout Plan
1. Land directory skeleton and example configs.
2. Wire up local Compose overlay and smoke test.
3. Add K8s manifests; deploy to staging with limited traffic; validate HPA scaling and health.
4. Configure secrets via the organization’s secret manager; rotate keys; validate virtual key budgets.
5. Enable observability dashboards and alerts (Prometheus/Datadog), including error rate and 429 alerts.
6. Gradually route traffic from existing LLM calls to the proxy; monitor; ramp to 100%.
7. Post-rollout: document SLOs, runbooks, and on-call guidelines in `services/llm_proxy/README.md`.

Rollback: Keep prior deployment revision; disable ingress/routes; revert config to last-known-good; drain and scale down.

---

## Risks & Mitigations
- Misconfigured Redis (pool exhaustion): use individual host/port/password and conservative pool limits.
- Over-aggressive multi-worker: standardize on single worker per pod.
- Secret leakage in logs: enforce structured logs without sensitive fields; redaction filters.
- Database unavailability: allow graceful degradation with queueing/batch retries; Redis buffering.
- Provider quota throttling: cross-account quotas (AWS Bedrock), fallback chains, and budget caps on virtual keys.

---

## Acceptance Criteria (Go/No-Go)
- Local: `docker compose` up, health endpoints pass, smoke test returns 200.
- K8s: Deployment green with readiness gating DB/Redis; HPA scales on CPU; health app separate.
- Security: non-root image, secrets via manager, `LITELLM_MASTER_KEY` valid, TLS at ingress.
- Observability: metrics scraped, dashboards live, basic alerts configured.
- Performance: p50 ≤ 100ms overhead, sustained ≥ 100 RPS per pod with no 429 at configured quotas.

---

## Next Steps
- Implement the directory skeleton and example files.
- Add smoke/load scripts and integrate minimal CI checks.
- Prepare staging deployment and validate with a single provider (Azure OpenAI), then add others.



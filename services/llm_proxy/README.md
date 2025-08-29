# LiteLLM Proxy Service

This service runs a production-ready LiteLLM proxy, providing an OpenAI-compatible gateway for multiple LLM providers with routing, fallbacks, and Redis-backed coordination.

## Features
- OpenAI-compatible API (`/v1/*`)
- Usage-based routing with fallbacks
- Single-worker performance model
- Separate health app endpoints
- PostgreSQL persistence with batch writes
- Redis for coordination/cache

## Quickstart (Docker Compose)

1) Copy config and set env:
```bash
cp services/llm_proxy/config/litellm_config.example.yaml services/llm_proxy/config/litellm_config.yaml
cp services/llm_proxy/.env.example services/llm_proxy/.env
```

2) Start services:
```bash
docker compose -f docker-compose.yml -f services/llm_proxy/compose/docker-compose.override.yml --env-file services/llm_proxy/.env up -d
```

3) Smoke test:
```bash
services/llm_proxy/scripts/smoke.sh
```

Health:
- http://localhost:4000/health
- http://localhost:4000/health/liveliness
- http://localhost:4000/health/readiness

## Kubernetes

Manifests are in `services/llm_proxy/k8s/`:
- `configmap.yaml`, `secret.yaml`, `deployment.yaml`, `service.yaml`, `hpa.yaml`, optional `networkpolicy.yaml`, `ingress.yaml`.

Apply:
```bash
kubectl apply -f services/llm_proxy/k8s/
```

## Environment Variables
See `.env.example`. Critical:
- `LITELLM_MASTER_KEY` (must start with `sk-`)
- `DATABASE_URL`
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`
- Provider credentials (e.g., `AZURE_API_KEY`, `AZURE_API_BASE`, `AZURE_DEPLOYMENT_NAME`)

## Security
- Use non-root images in production
- Store secrets in a secret manager; k8s Secrets as delivery only
- Set `LITELLM_SALT_KEY` before first use for encryption

## Observability
- Enable Prometheus/Datadog scraping
- Prefer structured JSON logs

## Notes
- Single Uvicorn worker per container recommended
- Avoid `redis_url`; set host/port/password individually
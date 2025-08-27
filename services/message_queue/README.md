# Message Queue Service

This service implements a single-queue-per-organization design using RabbitMQ priority queues, with a demo producer, worker, and agent coordinator.

## Prerequisites
- Docker & Docker Compose
- Python 3.11+

## Local development
```bash
cd services/message_queue
uv venv
uv sync
source .venv/bin/activate
```

## Bring up infra
Use the monorepo compose at the repository root:
```bash
# from repo root
cp .env.example .env   # then edit SUPABASE_*, ORG_ID, AGENT_ID as needed
docker compose up -d rabbitmq
```
RabbitMQ UI: `http://localhost:15672` (guest/guest)

## Configure Supabase (local)
Set environment for your local Supabase instance:
```bash
export SUPABASE_URL="http://localhost:54321"
export SUPABASE_SERVICE_ROLE_KEY="<local-service-role-key>"
```
Apply the schema in `supabase_schema.sql` using the Supabase SQL Editor.

## Initialize topology
```bash
export ORG_IDS=demo-org
uv run python -m scripts.init_topology
```

## Run coordinator (prints demo-agent responses)
```bash
# Using Docker (recommended for quick start)
docker compose run --rm coordinator

# Or run locally in venv
export AGENT_IDS=${AGENT_ID:-demo-agent}
uv run python -m scripts.coordinator
```

## Run worker (consumes demo-org queue)
```bash
# Using Docker (recommended for quick start)
docker compose run --rm \
  -e ORG_ID=${ORG_ID:-demo-org} \
  -e AGENT_ID=${AGENT_ID:-demo-agent} \
  worker

# Or run locally in venv
export ORG_ID=${ORG_ID:-demo-org}
export AGENT_ID=${AGENT_ID:-demo-agent}
uv run python -m scripts.worker
```
The worker exposes Prometheus metrics on `http://localhost:9000/metrics` by default.

## Send a test message
```bash
export ORG_ID=demo-org
export PRIORITY=0   # P0..P3 as 0..3
export TYPE=agent_message
uv run python -m scripts.producer
```

## Environment
Copy `.env.example` to `.env` in the repo root and set:

- `SUPABASE_URL`: your Supabase URL (e.g., `http://localhost:54321` for local)
- `SUPABASE_SERVICE_ROLE_KEY`: service role key
- `ORG_ID`: default org for local runs
- `AGENT_ID`: default agent for local runs


## Kubernetes
See `docs/DEPLOYMENT_K8S.md` for a checklist and manifests.

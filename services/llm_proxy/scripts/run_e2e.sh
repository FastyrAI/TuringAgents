#!/usr/bin/env bash
set -euo pipefail

# Run llm_proxy E2E tests

ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/../../.. && pwd)
pushd "$ROOT_DIR" >/dev/null

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required to run E2E tests (for compose up)." >&2
  exit 1
fi

ENV_FILE="services/llm_proxy/.env"
EXAMPLE_FILE="services/llm_proxy/.env.example"

if [ ! -f "$ENV_FILE" ]; then
  echo "[e2e] No .env found. Preparing environment file..."
  if [ -f "$EXAMPLE_FILE" ]; then
    cp "$EXAMPLE_FILE" "$ENV_FILE"
  else
    cat > "$ENV_FILE" <<'EOF'
LITELLM_MASTER_KEY=sk-dev-1234
DATABASE_URL=postgresql://llmproxy:pass@db:5432/litellm
AZURE_API_KEY=
AZURE_API_BASE=
AZURE_DEPLOYMENT_NAME=
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
SEPARATE_HEALTH_APP=1
EOF
  fi
fi

echo "[e2e] Starting LiteLLM via docker compose..."
docker compose -f docker-compose.yml -f services/llm_proxy/compose/docker-compose.override.yml --env-file "$ENV_FILE" up -d

echo "[e2e] Installing test dependencies..."
python -m pip install -e services/llm_proxy[test]

echo "[e2e] Running pytest..."
pytest -q services/llm_proxy/tests/e2e

echo "[e2e] Done"

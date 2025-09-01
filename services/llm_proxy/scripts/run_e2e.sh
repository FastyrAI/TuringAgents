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
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
SEPARATE_HEALTH_APP=1
EOF
  fi
fi

# Ensure a litellm config file exists for compose mount
CONFIG_EXAMPLE="services/llm_proxy/config/litellm_config.example.yaml"
CONFIG_FILE="services/llm_proxy/config/litellm_config.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
  echo "[e2e] No config found at $CONFIG_FILE. Copying example..."
  cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
fi

echo "[e2e] Rendering config from example with env vars..."
python services/llm_proxy/scripts/render_config.py \
  --in services/llm_proxy/config/litellm_config.example.yaml \
  --out services/llm_proxy/config/litellm_config.yaml \
  --env services/llm_proxy/.env

echo "[e2e] Starting LiteLLM via docker compose (only required services)..."
docker compose \
  -f docker-compose.yml \
  -f services/llm_proxy/compose/docker-compose.override.yml \
  --env-file "$ENV_FILE" \
  up -d litellm db redis

echo "[e2e] Installing test dependencies (wheels only)..."
python -m pip install -U pip setuptools wheel
python -m pip install --only-binary=:all: -U \
  httpx==0.27.2 \
  pytest==8.3.3 \
  python-dotenv==1.0.1

echo "[e2e] Running pytest..."
pytest -q services/llm_proxy/tests/e2e

echo "[e2e] Done"

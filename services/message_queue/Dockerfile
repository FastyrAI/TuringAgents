FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv==0.4.20

# Copy project
COPY pyproject.toml /app/
COPY libs /app/libs
COPY scripts /app/scripts
COPY tests /app/tests

# Install deps
RUN uv venv && . .venv/bin/activate && uv sync

# Default to worker
ENV ORG_ID=demo-org \
    AGENT_ID=demo-agent \
    METRICS_PORT=9000

CMD ["bash", "-lc", ". .venv/bin/activate && python -m scripts.worker"]



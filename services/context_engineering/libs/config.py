from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel


# Load variables from a local .env if present
load_dotenv()


EnvName = Literal["development", "staging", "production"]
ScopeName = Literal["session", "goal", "global"]


# Core services
NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")

RABBITMQ_URL: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

# Environment
ENVIRONMENT: EnvName = os.getenv("ENVIRONMENT", "development").lower()  # type: ignore[assignment]
METRICS_PORT: int = int(os.getenv("METRICS_PORT", "9101"))

# Optional LLM providers
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# Governance + TTL
EPHEMERAL_TTL_SECONDS: int = int(os.getenv("EPHEMERAL_TTL_SECONDS", str(60 * 60 * 24)))  # 24h default


class Settings(BaseModel):
    environment: EnvName = ENVIRONMENT
    neo4j_uri: str = NEO4J_URI
    neo4j_user: str = NEO4J_USER
    neo4j_password: str = NEO4J_PASSWORD
    rabbitmq_url: str = RABBITMQ_URL
    metrics_port: int = METRICS_PORT
    openai_api_key: str = OPENAI_API_KEY
    anthropic_api_key: str = ANTHROPIC_API_KEY
    gemini_api_key: str = GEMINI_API_KEY
    ephemeral_ttl_seconds: int = EPHEMERAL_TTL_SECONDS


def is_prod() -> bool:
    return ENVIRONMENT == "production"


def get_settings() -> Settings:
    return Settings()

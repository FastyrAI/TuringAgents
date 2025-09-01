#!/usr/bin/env python3
"""
Render LiteLLM config by expanding ${VAR} placeholders from the example
template using values from services/llm_proxy/.env and the current
environment, writing the standard litellm_config.yaml used by the container.

Why:
- LiteLLM does not expand environment variables inside YAML. Without rendering,
  placeholders like ${DATABASE_URL} remain literal and break startup.

Usage:
  $ python services/llm_proxy/scripts/render_config.py \
      --in services/llm_proxy/config/litellm_config.example.yaml \
      --out services/llm_proxy/config/litellm_config.yaml \
      --env services/llm_proxy/.env

Example:
  $ python services/llm_proxy/scripts/render_config.py

This will use sensible defaults for --in/--out/--env under the repo root.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def parse_dotenv_file(env_path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file into a dict without external deps.

    - Ignores blank lines and lines starting with '#'.
    - Supports unquoted or quoted values.

    Examples
    --------
    >>> parse_dotenv_file(Path('example.env'))  # doctest: +SKIP
    {'FOO': 'bar', 'BAZ': 'qux'}
    """
    env: dict[str, str] = {}
    if not env_path.exists():
        return env
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (value.startswith("'") and value.endswith("'")) or (
            value.startswith('"') and value.endswith('"')
        ):
            value = value[1:-1]
        env[key] = value
    return env


def expand_vars(text: str, env: dict[str, str]) -> str:
    """Expand $VAR and ${VAR} using provided env; unknown vars are left intact.

    This uses os.path.expandvars which leaves unknown variables unchanged,
    preserving placeholders if a value is not provided.

    Examples
    --------
    >>> expand_vars('Hello ${NAME}', {'NAME': 'World'})
    'Hello World'
    """
    # Merge provided env into process env for expandvars
    merged = os.environ.copy()
    merged.update(env)
    # Temporarily swap os.environ for expansion
    original_environ = os.environ
    try:
        os.environ = merged  # type: ignore[assignment]
        return os.path.expandvars(text)
    finally:
        os.environ = original_environ  # type: ignore[assignment]


def main() -> None:
    """CLI entrypoint to render a resolved LiteLLM config.

    Resolves default paths relative to repo root. Call with --help for options.
    """
    parser = argparse.ArgumentParser(description="Render LiteLLM config with env vars")
    default_in = Path("services/llm_proxy/config/litellm_config.example.yaml")
    default_out = Path("services/llm_proxy/config/litellm_config.yaml")
    default_env = Path("services/llm_proxy/.env")
    parser.add_argument("--in", dest="input_path", type=Path, default=default_in,
                        help=f"Input template YAML (default: {default_in})")
    parser.add_argument("--out", dest="output_path", type=Path, default=default_out,
                        help=f"Output resolved YAML (default: {default_out})")
    parser.add_argument("--env", dest="env_path", type=Path, default=default_env,
                        help=f".env file to load (default: {default_env})")
    args = parser.parse_args()

    # Load env from file (if present) and merge into expansion context
    file_env = parse_dotenv_file(args.env_path)

    # Read template YAML and expand placeholders
    raw = args.input_path.read_text(encoding="utf-8")
    rendered = expand_vars(raw, file_env)

    # Ensure output directory exists and write
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(rendered, encoding="utf-8")
    print(f"[render_config] Wrote: {args.output_path}")


if __name__ == "__main__":
    main()



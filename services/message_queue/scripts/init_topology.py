"""
Topology initializer.

- Declares per-org request (priority) and DLQ exchanges/queues
- Declares per-org retry exchanges and delay queues (DLX back to requests)
- Optionally pre-creates agent response exchanges/queues

New behavior:
- Supports a best-effort mode via ``--best-effort`` or ``INIT_TOPOLOGY_BEST_EFFORT=1``
  which will skip errors if RabbitMQ is not reachable (useful in Supabase-only CI).

Examples:
    uv run python -m scripts.init_topology
    uv run python -m scripts.init_topology --best-effort
"""

import asyncio
import os
import argparse
from typing import Sequence

from libs.config import RABBITMQ_URL
from libs.rabbit import declare_org_topology, declare_agent_response_topology, declare_org_retry_topology, connect


async def main(org_ids: Sequence[str], agent_ids: Sequence[str], best_effort: bool) -> None:
    """Declare the required RabbitMQ topology for the given orgs/agents.

    When ``best_effort`` is True, any connection or declaration error will
    be logged to stdout and the function will return successfully.
    """
    try:
        connection = await connect(RABBITMQ_URL)
    except Exception as exc:  # noqa: BLE001
        if best_effort:
            print(f"[init_topology] Skipping: RabbitMQ not reachable ({exc})")
            return
        raise

    async with connection:
        try:
            channel = await connection.channel()
            # Declare org request and DLQ topology
            for org in org_ids:
                await declare_org_topology(channel, org)
                await declare_org_retry_topology(channel, org)
            # Optionally pre-create agent response queues
            for agent in agent_ids:
                await declare_agent_response_topology(channel, agent)
        except Exception as exc:  # noqa: BLE001
            if best_effort:
                print(f"[init_topology] Skipping declarations due to error: {exc}")
                return
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Declare RabbitMQ topology for orgs/agents")
    parser.add_argument("--best-effort", action="store_true", help="Do not fail if RabbitMQ is unreachable")
    args = parser.parse_args()

    best_effort_env = os.getenv("INIT_TOPOLOGY_BEST_EFFORT", "false").lower() in {"1", "true", "yes"}
    best_effort = bool(args.best_effort or best_effort_env)

    orgs = os.getenv("ORG_IDS", "demo-org").split(",")
    agents = os.getenv("AGENT_IDS", "").split(",") if os.getenv("AGENT_IDS") else []
    asyncio.run(main(orgs, agents, best_effort))



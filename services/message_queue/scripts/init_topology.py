"""
Topology initializer.

- Declares per-org request (priority) and DLQ exchanges/queues
- Declares per-org retry exchanges and delay queues (DLX back to requests)
- Optionally pre-creates agent response exchanges/queues
"""

import asyncio
import os
from typing import Sequence

from libs.config import RABBITMQ_URL
from libs.rabbit import declare_org_topology, declare_agent_response_topology, declare_org_retry_topology, connect


async def main(org_ids: Sequence[str], agent_ids: Sequence[str]) -> None:
    """Declare the required RabbitMQ topology for the given orgs/agents."""
    connection = await connect(RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        # Declare org request and DLQ topology
        for org in org_ids:
            await declare_org_topology(channel, org)
            await declare_org_retry_topology(channel, org)
        # Optionally pre-create agent response queues
        for agent in agent_ids:
            await declare_agent_response_topology(channel, agent)


if __name__ == "__main__":
    orgs = os.getenv("ORG_IDS", "demo-org").split(",")
    agents = os.getenv("AGENT_IDS", "").split(",") if os.getenv("AGENT_IDS") else []
    asyncio.run(main(orgs, agents))



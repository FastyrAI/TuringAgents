import asyncio
import json
import os

from libs.config import RABBITMQ_URL
from libs.rabbit import declare_agent_response_topology, connect


async def main() -> None:
    agent_id = os.getenv("AGENT_ID", "demo-agent")
    connection = await connect(RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        await declare_agent_response_topology(channel, agent_id)
        queue = await channel.get_queue(f"agent.{agent_id}.responses.q")

        # Consume one message then exit
        incoming = await queue.get(no_ack=True, fail=False)
        if incoming:
            try:
                payload = json.loads(incoming.body)
            except Exception:  # noqa: BLE001
                payload = {"malformed": True}
            print(json.dumps(payload))
        else:
            print(json.dumps({"empty": True}))


if __name__ == "__main__":
    asyncio.run(main())



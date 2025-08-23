## Turing Agents Monorepo

This repository hosts multiple services. The first service is the message queue.

### Layout
- `services/message_queue`: RabbitMQ-based message queue service (producer, worker, coordinator), plus docs and Supabase schema.
- `docker-compose.yml`: Infra and service containers for local dev.

### Getting started
From the repo root:
```bash
docker compose up -d rabbitmq
```
Then follow `services/message_queue/README.md` for running the service locally, tests, and deployment notes.

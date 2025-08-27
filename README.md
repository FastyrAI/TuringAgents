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

### Running the message queue components
- Worker:
  - Docker: `docker compose run --rm worker`
  - Local: see `services/message_queue/README.md`
- Coordinator:
  - Docker: `docker compose run --rm coordinator`
  - Local: see `services/message_queue/README.md`

### Tests
Run unit tests for the message queue service via:
```bash
./scripts/test_message_queue.sh
```

# Security Hardening (RabbitMQ + K8s)

This doc covers programmatic setup for RabbitMQ vhosts/users/permissions and how to point the app at a TLS-enabled broker. TLS enablement itself is typically handled by your platform (Helm chart/Ingress/Operator) and is out of scope here; we assume your RabbitMQ endpoint supports TLS (amqps).

## Programmatic RabbitMQ setup (vhost/user/permissions)

Artifacts provided:
- `k8s/rabbitmq-admin-secret.example.yaml`: template Secret with management API URL/credentials, target vhost, app user, and permissions
- `scripts/rabbit_setup.py`: Management API client that creates the vhost, user, and permissions and prints a ready-to-use amqps URL

Populate the Secret with your values, then run the setup job/process. The script prints a JSON object with an `amqps_url` you can use for `RABBITMQ_URL` in deployments.

Environment variables expected by the setup script (supplied via Secret/env):
- `RABBITMQ_MGMT_URL`: Management API base URL (http/https)
- `RABBITMQ_ADMIN_USER`, `RABBITMQ_ADMIN_PASS`: Admin credentials
- `RABBITMQ_SETUP_VHOST`: Target vhost to create (e.g. `/prod`)
- `RABBITMQ_SETUP_USER`, `RABBITMQ_SETUP_PASS`: App user credentials
- `RABBITMQ_PERMISSIONS_CONFIGURE`, `RABBITMQ_PERMISSIONS_WRITE`, `RABBITMQ_PERMISSIONS_READ`: Permission regexes
- (Optional) `RABBITMQ_AMQPS_HOST`, `RABBITMQ_AMQPS_PORT`: Host/port to compose the connection URL; defaults: `rabbitmq`, `5671`

## TLS (amqps) overview
- Use a TLS-enabled RabbitMQ endpoint (amqps).
- Prefer per-environment vhosts and least-privilege users.
- Store `RABBITMQ_URL` as a secret: `amqps://<user>:<pass>@<host>:5671/<vhost>`.
- If your broker requires client auth (mTLS), mount the CA/cert/key via K8s Secrets and configure your sidecar or client accordingly.

## App configuration
- Producer/Worker/Coordinator use `RABBITMQ_URL`. For TLS, set it to the `amqps_url` emitted by the setup script.
- No code changes are needed between dev and prod; use plain `amqp://` locally and `amqps://` in secure environments.

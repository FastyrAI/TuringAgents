# Docker deployment guide for LiteLLM proxy microservices

LiteLLM proxy can be deployed as a production-ready containerized microservice using official Docker images from GitHub Container Registry, with comprehensive support for Kubernetes orchestration, auto-scaling, and enterprise security configurations. The proxy provides **three main deployment patterns**: simple single-container setups, multi-instance clusters with Redis coordination, and full Kubernetes deployments with horizontal pod autoscaling supporting up to 360,000 requests per hour per instance.

## Official Docker images and deployment methods

LiteLLM maintains official Docker images on GitHub Container Registry (GHCR), providing multiple specialized variants for different deployment scenarios. The **`ghcr.io/berriai/litellm:main-stable`** image serves as the production-recommended option, undergoing 12-hour load tests before release. For database-optimized deployments, the `ghcr.io/berriai/litellm-database:main-stable` variant includes pre-configured Prisma binaries and connection pooling optimizations. Security-conscious deployments can leverage the `ghcr.io/berriai/litellm-non_root:main-stable` image, which runs with restricted permissions.

The basic deployment pattern mounts a configuration file and exposes port 4000:

```bash
docker run \
  -v $(pwd)/litellm_config.yaml:/app/config.yaml \
  -e AZURE_API_KEY=your_key \
  -e AZURE_API_BASE=your_endpoint \
  -p 4000:4000 \
  ghcr.io/berriai/litellm:main-stable \
  --config /app/config.yaml --detailed_debug
```

For cloud-native deployments, LiteLLM supports **configuration storage in S3 or Google Cloud Storage**, eliminating the need for local volume mounts. The proxy can fetch configurations directly from cloud storage using environment variables like `LITELLM_CONFIG_BUCKET_NAME` and `LITELLM_CONFIG_BUCKET_OBJECT_KEY`, enabling dynamic configuration updates without container restarts.

The official Dockerfile utilizes **Chainguard's hardened Python base image** (`cgr.dev/chainguard/python:latest-dev`), providing a minimal attack surface with zero critical vulnerabilities. The multi-stage build process optimizes image size while including essential components like the admin UI, Prisma database client, and supervisord for process management.

## Microservice architecture patterns and best practices

LiteLLM proxy excels as a microservice gateway, implementing several key patterns for production deployments. The **usage-based routing strategy** (`usage-based-routing-v2`) intelligently distributes requests across multiple LLM endpoints based on rate limits and current usage, preventing 429 errors and maximizing throughput. This routing layer supports **fallback chains**, automatically switching from primary models like GPT-4 to alternatives when failures occur.

For high availability, the recommended architecture deploys **multiple LiteLLM instances behind a load balancer**, with Redis providing shared state management. Each instance runs a single Uvicorn worker (avoiding multi-worker configurations that reduce performance by 20-30%). The proxy implements **circuit breaker patterns** with configurable cooldown periods - after three consecutive failures, an endpoint enters a 30-second cooldown before retry attempts resume.

Production deployments benefit from **separate health check processes** on port 8001, preventing health endpoint failures during high load. This architectural decision ensures Kubernetes doesn't unnecessarily restart healthy pods experiencing temporary load spikes. The proxy also supports **pre-call health checks**, validating model availability before routing requests, reducing latency for failed requests by 150ms on average.

Database persistence follows a **batch write pattern**, accumulating metrics and logs for 60-second intervals before bulk insertion. This reduces database load by 80% compared to real-time writes while maintaining data consistency through Redis-backed transaction buffers.

## Configuration options and environment variables

The proxy configuration system operates through three layers: environment variables, YAML configuration files, and runtime API calls. **Critical environment variables** include `LITELLM_MASTER_KEY` for authentication (must start with 'sk-'), `DATABASE_URL` for PostgreSQL connections, and `LITELLM_SALT_KEY` for credential encryption.

The comprehensive YAML configuration structure supports model definitions with rate limiting:

```yaml
model_list:
  - model_name: gpt-4o
    litellm_params:
      model: azure/deployment-name
      api_base: os.environ/AZURE_API_BASE
      api_key: os.environ/AZURE_API_KEY
      rpm: 60  # Requests per minute
      tpm: 100000  # Tokens per minute

general_settings:
  master_key: sk-1234
  database_url: postgresql://user:pass@host:5432/litellm
  database_connection_pool_limit: 10
  proxy_batch_write_at: 60

router_settings:
  routing_strategy: usage-based-routing-v2
  redis_host: os.environ/REDIS_HOST
  redis_port: 6379
  redis_password: os.environ/REDIS_PASSWORD
```

Performance-critical configurations include **`database_connection_pool_limit`** (recommended: 10-20 connections), **`max_parallel_requests`** (per-instance limit), and **`proxy_batch_write_at`** (database write interval). Security parameters like `LITELLM_SALT_KEY` must be set before first deployment and cannot change afterward without re-encrypting stored credentials.

## Production deployment configurations

### Kubernetes orchestration with horizontal scaling

The production Kubernetes deployment implements comprehensive reliability features:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: litellm-deployment
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: litellm-container
        image: ghcr.io/berriai/litellm:main-stable
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health/liveliness
            port: 4000
          initialDelaySeconds: 120
          periodSeconds: 15
        readinessProbe:
          httpGet:
            path: /health/readiness
            port: 4000
          initialDelaySeconds: 30
          periodSeconds: 10
```

The **Horizontal Pod Autoscaler** configuration targets 70% CPU utilization, scaling between 2-10 replicas based on load. Health checks utilize distinct endpoints - `/health/liveliness` for container restarts and `/health/readiness` for load balancer routing decisions. The readiness probe includes database connectivity validation, ensuring traffic only routes to fully operational instances.

### Docker Compose for multi-container deployments

Production Docker Compose configurations integrate PostgreSQL, Redis, and monitoring:

```yaml
version: "3.9"
services:
  litellm:
    image: ghcr.io/berriai/litellm:main-stable
    ports:
      - "4000:4000"
    environment:
      DATABASE_URL: "postgresql://llmproxy:pass@db:5432/litellm"
      LITELLM_MASTER_KEY: "sk-1234"
      REDIS_HOST: "redis"
      SEPARATE_HEALTH_APP: "1"
    depends_on:
      - db
      - redis
    healthcheck:
      test: ["CMD-SHELL", "wget --no-verbose --tries=1 http://localhost:4000/health"]
      interval: 30s
      timeout: 10s

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 1gb --maxmemory-policy allkeys-lru
```

The configuration implements **service dependencies**, ensuring database and cache availability before proxy startup. Health checks prevent premature traffic routing, while Redis memory limits and eviction policies optimize cache performance.

## Security hardening and performance optimization

Security best practices begin with **non-root container execution** using the dedicated `litellm-non_root` image variant. API keys integrate with external secret management systems including AWS Secrets Manager, Google Secret Manager, and HashiCorp Vault through the `key_management_system` configuration. Virtual keys support **granular access control**, limiting models, budgets, and rate limits per key.

Performance optimization centers on **single-worker deployments** - running one Uvicorn worker per container provides optimal throughput. Redis configuration requires individual host/port/password parameters rather than connection strings, improving connection pooling by 80 RPS. The **`SEPARATE_HEALTH_APP`** environment variable isolates health checks from main traffic, preventing false-positive failures during load spikes.

Caching strategies leverage **Redis with semantic similarity matching**, reducing LLM API calls by up to 40% for repetitive queries. The cache supports TTL configuration, namespace isolation, and cluster deployments for high availability. Database optimizations include **connection pooling limits** (10 connections recommended), **batch writes** (60-second intervals), and **graceful degradation** when database becomes unavailable in VPC deployments.

Security scanning via **Grype, Snyk, and Trivy** validates zero critical vulnerabilities in production images. TLS/SSL configuration supports certificate validation, custom security levels, and mTLS for service mesh deployments. Rate limiting operates at multiple levels - model, team, user, and global - with Redis-backed coordination across instances.

## Real-world deployment patterns and recommendations

Production deployments demonstrate consistent performance characteristics: **50ms median latency**, **100 requests/second throughput**, and **99.9% availability** with proper configuration. Multi-region deployments leverage **cross-account IAM roles** for AWS Bedrock, distributing quota across accounts to eliminate throttling. The least-busy routing strategy proves most effective for geographically distributed endpoints.

Critical anti-patterns to avoid include **using `redis_url` instead of individual parameters** (causes connection pool exhaustion), **running multiple workers per container** (reduces performance 30%), and **enabling verbose logging in production** (increases latency 20ms). The recommended monitoring stack combines **Prometheus metrics** for infrastructure, **Datadog for LLM observability**, and **structured JSON logging** for troubleshooting.

Enterprise deployments benefit from **Helm chart automation**, supporting GitOps workflows with ArgoCD. The chart includes migration jobs, configurable resource limits, and multi-environment value files. AWS ECS deployments utilize **Fargate spot instances** for cost optimization, achieving 70% savings while maintaining SLA requirements through proper health checks and auto-scaling policies.

## Conclusion

LiteLLM proxy provides a production-ready foundation for containerized LLM gateway deployments, combining enterprise security, intelligent routing, and horizontal scalability. The official Docker images, comprehensive configuration system, and proven architectural patterns enable organizations to deploy resilient microservices handling hundreds of thousands of requests per hour. Success requires careful attention to single-worker configurations, Redis-based state management, and proper health check isolation - following these documented patterns ensures optimal performance and reliability in production environments.
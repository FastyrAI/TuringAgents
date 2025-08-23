## Kubernetes Deployment (Defer Until Ready)

This project can run locally without Kubernetes. When you're ready to deploy to a cluster, follow these steps.

### Prerequisites
- A container registry you can push to (Docker Hub, GHCR, ECR, GCR, etc.)
- RabbitMQ accessible from the cluster (AMQP URL)
- Supabase URL + service role key
- Optional autoscaling: KEDA installed in the cluster

### Build and push the worker image
```bash
export IMAGE=<registry>/turing-agents-worker:latest
docker build -t "$IMAGE" .
docker push "$IMAGE"
```

### Create namespace (one per org)
```bash
export NS=demo-org
kubectl create namespace "$NS" || true
```

### Create secrets for RabbitMQ and Supabase
```bash
kubectl -n "$NS" create secret generic ta-secrets \
  --from-literal=RABBITMQ_URL='amqp://guest:guest@<rabbit-host>:5672/%2F' \
  --from-literal=SUPABASE_URL='https://<your-project>.supabase.co' \
  --from-literal=SUPABASE_SERVICE_ROLE_KEY='<service-role-key>' \
  --dry-run=client -o yaml | kubectl apply -f -
```

### Deploy the worker and expose metrics
1) Edit `k8s/worker-deployment.yaml` and set the image to `$IMAGE`.
2) Apply:
```bash
kubectl -n "$NS" apply -f k8s/worker-deployment.yaml
kubectl -n "$NS" rollout status deployment/ta-worker
```

### (Optional) Enable autoscaling with KEDA
1) Install KEDA (see docs: `https://keda.sh/docs/latest/deploy/`).
2) Update `k8s/keda-scaledobject.yaml` (queueName per org) and apply:
```bash
kubectl -n "$NS" apply -f k8s/keda-scaledobject.yaml
```

### Verify
```bash
kubectl -n "$NS" get pods
kubectl -n "$NS" logs deploy/ta-worker -f
kubectl -n "$NS" port-forward svc/ta-worker-metrics 9000:9000
curl -s http://localhost:9000/metrics | head
```

If you're not deploying now, keep this file as your future checklist.



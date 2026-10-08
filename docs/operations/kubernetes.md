# Operations · Kubernetes (openKMS)

Deploy the stock SPA + API onto a cluster registered in **openKMS Console → Kubernetes**, then register the frontend Service as a hosted App.

Postgres stays **external** (not in-cluster). openKMS `kubernetes apply` only allows Deployment / Service / Pod / ConfigMap — **no PVC or Secret**. Create the Namespace (kubectl) and Secret (cluster Console / kubectl) out of band.

## Prerequisites

- openKMS skill CLI (`python ~/.claude/skills/openkms/scripts/cli.py` or project `.openkms/skills/openkms/…`)
- Cluster registered and healthy (`kubernetes clusters list`)
- External Postgres reachable from pods (OrbStack: `host.docker.internal`)
- Namespace `stock` and Secret `stock-secrets` already present in the cluster

## Layout

| File | Role |
|---|---|
| `k8s/namespace.yaml` | Namespace `stock` — **kubectl** (if not created yet) |
| `k8s/app.yaml` | ConfigMap + backend/frontend Deployment & Service — openKMS apply |

Images: `turtle-backend:latest`, `turtle-frontend:latest` (`imagePullPolicy: IfNotPresent`). Frontend image is built with `VITE_BASE=./` so assets and API calls work under the openKMS service proxy (HashRouter).

## Configure

**ConfigMap** (`stock-config` in `k8s/app.yaml`) — non-secret settings:

| Key | Typical local value |
|---|---|
| `STOCK_DATABASE_HOST` | `host.docker.internal` |
| `STOCK_DATABASE_PORT` | `5432` |
| `STOCK_DATABASE_USER` / `NAME` | match your external DB |
| `STOCK_AUTH_MODE` | `none` (openKMS identity headers) |

**Secret** `stock-secrets` (created in the cluster, **not** checked into git):

| Key | Purpose |
|---|---|
| `STOCK_DATABASE_PASSWORD` | Postgres password |
| `STOCK_SECRET_KEY` | JWT signing (`local` mode; still set for consistency) |
| `TUSHARE_TOKEN` | Optional / legacy |

Backend pods mount both via `envFrom` (ConfigMap + Secret).

## Build → apply → register-app

From repo root:

```bash
# 1. Images (OrbStack / local Docker)
./docker/build-base.sh   # once / when pyproject or package-lock changes
docker build -f docker/Dockerfile -t turtle-backend:latest .
docker build -f docker/Dockerfile.frontend \
  --build-arg VITE_BASE=./ \
  -t turtle-frontend:latest .

# 2. Namespace if needed (Secret already exists in the cluster)
kubectl apply -f k8s/namespace.yaml

# 3. Workloads via openKMS
CLUSTER_ID=$(python ~/.claude/skills/openkms/scripts/cli.py kubernetes clusters list \
  | python -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])")

python ~/.claude/skills/openkms/scripts/cli.py kubernetes apply \
  --cluster-id "$CLUSTER_ID" \
  --file k8s/app.yaml \
  --namespace stock \
  --yes

# 4. Wait for pods, then register hosted App
python ~/.claude/skills/openkms/scripts/cli.py kubernetes pods \
  --cluster-id "$CLUSTER_ID" --namespace stock

python ~/.claude/skills/openkms/scripts/cli.py kubernetes register-app \
  --cluster-id "$CLUSTER_ID" \
  --namespace stock \
  --service frontend \
  --port 3200 \
  --name "股票交易系统" \
  --api-name stockTrading \
  --yes
```

Open the app from openKMS **Apps**. Traffic goes through the API-server Service proxy (no kubeconfig in the browser). WebSocket is not proxied.

## Update / tear down

```bash
python … kubernetes apply --cluster-id "$CLUSTER_ID" --file k8s/app.yaml --namespace stock --yes
kubectl -n stock rollout restart deploy/backend deploy/frontend
```

Delete workloads (leave cluster Secret as you manage it):

```bash
python … kubernetes delete --cluster-id "$CLUSTER_ID" --kind Service --name frontend --namespace stock --yes
python … kubernetes delete --cluster-id "$CLUSTER_ID" --kind Service --name backend --namespace stock --yes
python … kubernetes delete --cluster-id "$CLUSTER_ID" --kind Deployment --name frontend --namespace stock --yes
python … kubernetes delete --cluster-id "$CLUSTER_ID" --kind Deployment --name backend --namespace stock --yes
python … kubernetes delete --cluster-id "$CLUSTER_ID" --kind ConfigMap --name stock-config --namespace stock --yes
kubectl delete -f k8s/namespace.yaml   # optional; removes namespace and in-ns objects
```

## See also

- [Operations · Docker](docker.md)
- [Configuration](../features/configuration.md)
- openKMS skill `references/kubernetes.md`

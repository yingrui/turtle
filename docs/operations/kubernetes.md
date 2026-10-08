# Operations · Kubernetes (openKMS)

Deploy the stock SPA + API onto a cluster registered in **openKMS Console → Kubernetes**, then register the frontend Service as a hosted App.

Postgres stays **external** (not in-cluster). openKMS `kubernetes apply` only allows Deployment / Service / Pod / ConfigMap — no PVC or Secret.

## Prerequisites

- openKMS skill CLI (`python ~/.claude/skills/openkms/scripts/cli.py` or project `.openkms/skills/openkms/…`)
- Cluster registered and healthy (`kubernetes clusters list`)
- External Postgres reachable from pods (OrbStack: `host.docker.internal`)
- `kubectl` only to create the namespace (cluster-scoped objects are rejected by openKMS apply)

## Layout

| File | Role |
|---|---|
| `k8s/namespace.yaml` | Namespace `stock` — apply with **kubectl** |
| `k8s/app.yaml` | ConfigMap + backend/frontend Deployment & Service |

Images: `turtle-backend:latest`, `turtle-frontend:latest` (`imagePullPolicy: IfNotPresent`). Frontend image is built with `VITE_BASE=./` so assets and API calls work under the openKMS service proxy (HashRouter).

## Configure DB

Edit `STOCK_DATABASE_*` (and secrets) in `k8s/app.yaml` ConfigMap `stock-config` before apply. Defaults target OrbStack → host Postgres:

| Key | Typical local value |
|---|---|
| `STOCK_DATABASE_HOST` | `host.docker.internal` |
| `STOCK_DATABASE_PORT` | `5432` |
| `STOCK_DATABASE_USER` / `PASSWORD` / `NAME` | match your external DB |

## Build → apply → register-app

From repo root:

```bash
# 1. Images (OrbStack / local Docker)
./docker/build-base.sh   # once / when pyproject or package-lock changes
docker build -f docker/Dockerfile -t turtle-backend:latest .
docker build -f docker/Dockerfile.frontend \
  --build-arg VITE_BASE=./ \
  -t turtle-frontend:latest .

# 2. Namespace (kubectl — not via openKMS)
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

Re-apply after ConfigMap or image changes:

```bash
docker build …   # as above
python … kubernetes apply --cluster-id "$CLUSTER_ID" --file k8s/app.yaml --namespace stock --yes
kubectl -n stock rollout restart deploy/backend deploy/frontend   # pick up new :latest digests
```

Delete workloads (openKMS):

```bash
python … kubernetes delete --cluster-id "$CLUSTER_ID" --kind Service --name frontend --namespace stock --yes
python … kubernetes delete --cluster-id "$CLUSTER_ID" --kind Service --name backend --namespace stock --yes
python … kubernetes delete --cluster-id "$CLUSTER_ID" --kind Deployment --name frontend --namespace stock --yes
python … kubernetes delete --cluster-id "$CLUSTER_ID" --kind Deployment --name backend --namespace stock --yes
python … kubernetes delete --cluster-id "$CLUSTER_ID" --kind ConfigMap --name stock-config --namespace stock --yes
kubectl delete -f k8s/namespace.yaml
```

## See also

- [Operations · Docker](docker.md)
- [Configuration](../features/configuration.md)
- openKMS skill `references/kubernetes.md`

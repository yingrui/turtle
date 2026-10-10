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
| `k8s/app.yaml` | ConfigMap + `backend` / `frontend` — **register-app** + hot reload |
| `k8s/app-dev.yaml` | Optional second pair if you want an isolated sync target |

| Image | Role |
|---|---|
| `turtle-backend` | API with `uvicorn --reload` + `POST /-/reload` |
| `turtle-frontend` | Vite DevServer for the hosted App (`VITE_BASE` = Service-proxy prefix) |
| `turtle-*-prod` | Compose / non-proxy production (nginx SPA, no watcher) |

**Why `VITE_BASE` + relative HTML:** the browser iframe is  
`/api/app-builder/apps/<appId>/proxy/` (openKMS `moduleAppProxyUrl`). openKMS then reaches
the Pod via the **Kubernetes API Service proxy**, which **rewrites absolute URLs in HTML**
and prefixes `/api/v1/namespaces/<ns>/services/<svc>:<port>/proxy/`. Absolute
`/api/app-builder/...` script tags become double-prefixed and 404 in the browser.

So: JS module graph still uses `VITE_BASE=/api/app-builder/apps/<appId>/proxy/`;
`vite.config.ts` rewrites **index.html** to relative `./@vite/client` / `./src/main.tsx`
(so the apiserver rewriter leaves them alone). After strip, the Pod re-attaches `VITE_BASE`
for Vite. WebSocket HMR is **not** proxied — after `dev-sync`, use `--reload`.

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

```bash
./docker/build-base.sh
./docker/build-images.sh

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/app.yaml
kubectl apply -f k8s/app-dev.yaml   # optional hot-sync pair

CLUSTER_ID=$(python ~/.claude/skills/openkms/scripts/cli.py kubernetes clusters list \
  | python -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])")

# Prefer openKMS apply when the API is healthy; otherwise kubectl as above.

python ~/.claude/skills/openkms/scripts/cli.py kubernetes register-app \
  --cluster-id "$CLUSTER_ID" \
  --namespace stock --service frontend --port 3200 \
  --name "股票交易系统" --api-name stockTrading --yes
```

Prefer registering **`frontend`** (not `frontend-dev`) as the hosted App.

## Hot reload (dev-sync)

```bash
python ~/.claude/skills/openkms/scripts/cli.py kubernetes dev-sync \
  --project-id "$PROJECT_ID" \
  --cluster-id "$CLUSTER_ID" \
  --namespace stock \
  --deployment backend-dev \
  --local-path backend/app \
  --container-path /app/backend/app \
  --reload --yes

python ~/.claude/skills/openkms/scripts/cli.py kubernetes dev-sync \
  --project-id "$PROJECT_ID" \
  --cluster-id "$CLUSTER_ID" \
  --namespace stock \
  --deployment frontend-dev \
  --local-path frontend/src \
  --container-path /src/src \
  --reload --yes
```

`--reload` posts to `/-/reload` in the Pod. Caps: ≤ 32 MiB packed; excludes `.git`, `node_modules`, `.venv`, `dist`, …

## Update / tear down

```bash
./docker/build-images.sh
kubectl apply -f k8s/app.yaml -f k8s/app-dev.yaml
kubectl -n stock rollout restart deploy/backend deploy/frontend deploy/backend-dev deploy/frontend-dev
```

## See also

- [Operations · Docker](docker.md)
- [Configuration](../features/configuration.md)
- openKMS skill `references/kubernetes.md`

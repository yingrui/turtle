#!/usr/bin/env bash
# Build app images (expects turtle-*-base already built via ./docker/build-base.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> turtle-backend:latest (dev/test, uvicorn --reload)"
docker build -f docker/Dockerfile --target backend -t turtle-backend:latest .

echo "==> turtle-backend-prod:latest (production)"
docker build -f docker/Dockerfile --target backend-prod -t turtle-backend-prod:latest .

echo "==> turtle-frontend:latest (dev/test, Vite)"
docker build -f docker/Dockerfile.frontend --target frontend \
  --build-arg VITE_BASE=./ \
  -t turtle-frontend:latest .

echo "==> turtle-frontend-prod:latest (production nginx SPA)"
docker build -f docker/Dockerfile.frontend --target frontend-prod \
  --build-arg VITE_BASE=./ \
  -t turtle-frontend-prod:latest .

echo "Done."
echo "  Dev/test K8s:  turtle-backend / turtle-frontend"
echo "  Production:    turtle-backend-prod / turtle-frontend-prod"

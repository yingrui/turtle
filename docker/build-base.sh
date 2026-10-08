#!/usr/bin/env bash
# Build dependency base images. Re-run when pyproject.toml or package-lock.json change.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> turtle-backend-base:latest"
docker build -f docker/Dockerfile.backend-base -t turtle-backend-base:latest .

echo "==> turtle-frontend-base:latest"
docker build -f docker/Dockerfile.frontend-base -t turtle-frontend-base:latest .

echo "Done. App images:"
echo "  docker build -f docker/Dockerfile -t turtle-backend:latest ."
echo "  docker build -f docker/Dockerfile.frontend --build-arg VITE_BASE=./ -t turtle-frontend:latest ."

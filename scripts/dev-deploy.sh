#!/usr/bin/env bash
# Hot-deploy code changes into the running cluster — no image build.
#
# The cluster already runs the reload-friendly variants: the backend serves with `uvicorn --reload`, the
# frontend runs the Vite dev server (`VITE_HMR=false`, so a page reload picks up new modules). What was
# missing is getting changed files in: this copies only what changed and pokes the backend's reload hook.
#
#   scripts/dev-deploy.sh backend    | frontend | both (default)
#
# Rebuild the image when dependencies or Dockerfiles change; use this when only code did.
set -euo pipefail

NS=${NS:-stock}
TARGET=${1:-both}
FULL=${FULL:-0}   # FULL=1 syncs everything (first use, or after switching branches)

sync_backend() {
  echo "→ backend: changed app/*.py → pod, then POST /-/reload"
  local files
  if [ "$FULL" = "1" ]; then
    files=$(cd backend && find app -name '*.py' | sort)
  else
    files=$(cd backend && git ls-files -m -o --exclude-standard app | grep -E '\.py$' || true)
  fi
  if [ -z "$files" ]; then
    echo "  (no changed python files)"
  else
    tar -C backend -cf - $files | kubectl -n "$NS" exec -i deploy/backend -- tar -C /app/backend -xf -
    echo "  copied: $(echo "$files" | tr '\n' ' ')"
  fi
  kubectl -n "$NS" exec deploy/backend -- curl -sf -X POST http://127.0.0.1:8200/-/reload >/dev/null || true
  echo "  reload requested"
}

sync_frontend() {
  echo "→ frontend: changed src/** → pod (Vite dev server serves them immediately)"
  local files
  if [ "$FULL" = "1" ]; then
    files=$(cd frontend && find src -type f \( -name '*.ts' -o -name '*.tsx' -o -name '*.scss' -o -name '*.css' -o -name '*.json' \) | sort)
  else
    files=$(cd frontend && git ls-files -m -o --exclude-standard src | grep -E '\.(tsx?|s?css|json)$' || true)
  fi
  if [ -z "$files" ]; then
    echo "  (no changed source files)"
  else
    tar -C frontend -cf - $files | kubectl -n "$NS" exec -i deploy/frontend -- tar -C /src -xf -
    echo "  copied: $(echo "$files" | tr '\n' ' ')"
  fi
}

case "$TARGET" in
  backend) sync_backend ;;
  frontend) sync_frontend ;;
  both) sync_backend; sync_frontend ;;
  *) echo "usage: $0 [backend|frontend|both]" >&2; exit 64 ;;
esac

echo "done"

#!/usr/bin/env bash
# Backend dev server — load env, install deps, run migrations, start uvicorn.
set -e

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$BACKEND_DIR/.." && pwd)"
cd "$BACKEND_DIR"

# Load .env (repo root, docker/, or backend/)
for envfile in "$REPO_ROOT/.env" "$REPO_ROOT/docker/.env" "$BACKEND_DIR/.env"; do
  if [[ -f "$envfile" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$envfile"
    set +a
    echo "stock: loaded $envfile"
    break
  fi
done

# Local path defaults (override in .env for Docker paths)
export STOCK_LOGS_DIR="${STOCK_LOGS_DIR:-$REPO_ROOT/logs}"
export STOCK_AUTH_MODE="${STOCK_AUTH_MODE:-local}"
export STOCK_ALLOW_SIGNUP="${STOCK_ALLOW_SIGNUP:-true}"
export STOCK_SECRET_KEY="${STOCK_SECRET_KEY:-stock-dev-secret-change-in-production}"
export STOCK_FRONTEND_URL="${STOCK_FRONTEND_URL:-http://localhost:3200}"
export PYTHONPATH="$BACKEND_DIR${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$STOCK_LOGS_DIR"

# Activate venv if present
if [[ -d "$BACKEND_DIR/.venv" ]]; then
  # shellcheck source=/dev/null
  source "$BACKEND_DIR/.venv/bin/activate"
elif [[ -d "$REPO_ROOT/.venv" ]]; then
  # shellcheck source=/dev/null
  source "$REPO_ROOT/.venv/bin/activate"
fi

stock_install_deps() {
  if command -v uv &>/dev/null; then
    echo "stock: installing deps (uv pip)..." >&2
    uv pip install -e "$BACKEND_DIR"
  elif python -m pip --version &>/dev/null; then
    echo "stock: installing deps (python -m pip)..." >&2
    python -m pip install -e "$BACKEND_DIR"
  else
    echo "stock: venv has no pip; running: python -m ensurepip" >&2
    python -m ensurepip --upgrade
    python -m pip install -e "$BACKEND_DIR"
  fi
}

if ! python -c "import app.main" 2>/dev/null; then
  stock_install_deps
  python -c "import app.main" || {
    echo "stock: import app.main still fails. Try:" >&2
    echo "  pip install -e $BACKEND_DIR" >&2
    exit 1
  }
fi

# pgvector (optional until vector features ship; required on pgvector/pgvector image)
if [[ -f "$BACKEND_DIR/scripts/ensure_pgvector.py" ]]; then
  python "$BACKEND_DIR/scripts/ensure_pgvector.py" || true
fi

# Schema: Alembic (same as Docker CMD) — use venv python -m alembic, not system alembic
python -m alembic upgrade head

exec python -m uvicorn app.main:app --reload --port 8200 \
  --reload-exclude '../logs/*' \
  --reload-exclude '../frontend/*'

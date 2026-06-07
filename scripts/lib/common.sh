# Shared helpers for MedAstraX setup and dev scripts.
# shellcheck shell=bash

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
VENV="$BACKEND/.venv"

log() { printf '==> %s\n' "$*"; }
warn() { printf '!! %s\n' "$*" >&2; }
die() { warn "$*"; exit 1; }

load_nvm() {
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  if [[ -s "$NVM_DIR/nvm.sh" ]]; then
    # shellcheck disable=SC1091
    . "$NVM_DIR/nvm.sh"
    return 0
  fi
  return 1
}

install_nvm() {
  log "Installing nvm (Node version manager)..."
  curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
  load_nvm || die "nvm install finished but nvm.sh is missing"
}

ensure_node() {
  if command -v npm >/dev/null 2>&1; then
    return 0
  fi

  if ! load_nvm; then
    install_nvm
  fi

  if [[ -f "$ROOT/.nvmrc" ]]; then
    log "Installing Node from .nvmrc..."
    nvm install
    nvm use
  else
    log "Installing Node LTS..."
    nvm install --lts
  fi

  command -v npm >/dev/null 2>&1 || die "npm still not available after nvm setup"
}

ensure_python() {
  command -v python3 >/dev/null 2>&1 || die "python3 not found (need Python 3.9+)"
  local version
  version="$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
  python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' \
    || die "Python 3.9+ required (found $version)"
}

ensure_env_file() {
  if [[ ! -f "$ROOT/.env" ]]; then
    cp "$ROOT/.env.example" "$ROOT/.env"
    log "Created .env from .env.example"
  fi
}

ensure_backend_venv() {
  ensure_python
  if [[ ! -d "$VENV" ]]; then
    log "Creating backend virtualenv..."
    python3 -m venv "$VENV"
  fi
}

activate_backend_venv() {
  ensure_backend_venv
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
}

install_backend_deps() {
  activate_backend_venv
  if [[ -f "$BACKEND/requirements-lock.txt" ]]; then
    log "Installing pinned Python dependencies..."
    pip install -q -r "$BACKEND/requirements-lock.txt"
  else
    warn "requirements-lock.txt missing; installing from pyproject.toml ranges"
  fi
  log "Installing hc-analytics package (editable)..."
  pip install -q -e "$BACKEND[dev]"
}

install_frontend_deps() {
  ensure_node
  if [[ ! -f "$FRONTEND/package-lock.json" ]]; then
    die "frontend/package-lock.json missing — run scripts/lock-deps.sh on a dev machine"
  fi
  log "Installing pinned frontend dependencies (npm ci)..."
  (cd "$FRONTEND" && npm ci --no-audit --no-fund)
}

frontend_ready() {
  [[ -d "$FRONTEND/node_modules" ]]
}

backend_ready() {
  [[ -x "$VENV/bin/python" ]] && "$VENV/bin/python" -c 'import hc_analytics' 2>/dev/null
}

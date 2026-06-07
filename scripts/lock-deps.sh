#!/usr/bin/env bash
# Regenerate pinned dependency lockfiles after changing pyproject.toml or package.json.
set -euo pipefail

# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

log "Refreshing Python lockfile..."
activate_backend_venv
pip install -q -e "$BACKEND[dev]"
pip freeze | grep -v '^hc-analytics' | grep -v '^-e ' | sort > "$BACKEND/requirements-lock.txt"
{
  echo "# Pinned Python dependencies for reproducible installs."
  echo "# Source of version ranges: backend/pyproject.toml"
  echo "# Regenerate: ./scripts/lock-deps.sh"
  echo "#"
  echo "# Install via: ./scripts/setup.sh  (recommended)"
  echo "# Or manually: pip install -r requirements-lock.txt && pip install -e \".[dev]\""
  echo ""
  cat "$BACKEND/requirements-lock.txt"
} > "$BACKEND/requirements-lock.txt.tmp"
mv "$BACKEND/requirements-lock.txt.tmp" "$BACKEND/requirements-lock.txt"

ensure_node
log "Refreshing frontend lockfile..."
(cd "$FRONTEND" && npm install --package-lock-only --no-audit --no-fund)

log "Lockfiles updated:"
echo "  backend/requirements-lock.txt"
echo "  frontend/package-lock.json"

#!/usr/bin/env bash
set -euo pipefail

# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

ensure_env_file

if ! backend_ready; then
  log "Backend not ready — running setup..."
  install_backend_deps
fi

activate_backend_venv
cd "$BACKEND"
exec uvicorn hc_analytics.api.app:app --reload --host "${HC_API_HOST:-127.0.0.1}" --port "${HC_API_PORT:-8000}"

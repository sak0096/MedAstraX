#!/usr/bin/env bash
set -euo pipefail

# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

ensure_env_file

if ! backend_ready || ! frontend_ready; then
  log "Dependencies missing — running setup..."
  "$ROOT/scripts/setup.sh"
fi

activate_backend_venv
load_nvm 2>/dev/null || true

echo ""
echo "Starting MedAstraX..."
echo "  API:       http://127.0.0.1:8000"
echo "  Dashboard: http://localhost:5173"
if [[ -f "$ROOT/.env" ]]; then
  echo "  Condition: $(grep -E '^HC_EXPERIMENTAL_CONDITION=' "$ROOT/.env" | cut -d= -f2 | cut -d' ' -f1 || echo baseline)"
fi
echo ""
echo "Press Ctrl+C to stop both servers."
echo ""

trap 'kill 0' EXIT

cd "$BACKEND"
uvicorn hc_analytics.api.app:app --reload --host 127.0.0.1 --port 8000 &
(cd "$FRONTEND" && npm run dev) &
wait

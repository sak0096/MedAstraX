#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "Created .env from .env.example"
fi

if [[ ! -d "$ROOT/backend/.venv" ]]; then
  echo "Creating backend virtualenv..."
  python3 -m venv "$ROOT/backend/.venv"
fi

source "$ROOT/backend/.venv/bin/activate"
pip install -e "$ROOT/backend[dev]" -q

if ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: npm not found. Install Node.js 18+ from https://nodejs.org/ then re-run."
  exit 1
fi

(cd "$ROOT/frontend" && npm install -q)

echo ""
echo "Starting MedAstraX..."
echo "  API:       http://127.0.0.1:8000"
echo "  Dashboard: http://localhost:5173"
echo "  Condition: $(grep HC_EXPERIMENTAL_CONDITION "$ROOT/.env" | cut -d= -f2 | cut -d' ' -f1)"
echo ""
echo "Press Ctrl+C to stop both servers."
echo ""

trap 'kill 0' EXIT

cd "$ROOT/backend"
uvicorn hc_analytics.api.app:app --reload --host 127.0.0.1 --port 8000 &
(cd "$ROOT/frontend" && npm run dev) &
wait

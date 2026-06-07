#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -e ".[dev]"

cd "$ROOT"
exec uvicorn hc_analytics.api.app:app --reload --host "${HC_API_HOST:-127.0.0.1}" --port "${HC_API_PORT:-8000}"

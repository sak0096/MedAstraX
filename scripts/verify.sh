#!/usr/bin/env bash
# Verify a fresh or existing install: tests, TypeScript build, API smoke check.
set -euo pipefail

# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

log "Verifying MedAstraX install..."

backend_ready || die "Backend not ready — run ./scripts/setup.sh first"
frontend_ready || die "Frontend not ready — run ./scripts/setup.sh first"

activate_backend_venv

log "Running backend tests..."
(cd "$BACKEND" && pytest -q)

load_nvm 2>/dev/null || true
log "Building frontend (TypeScript + Vite)..."
(cd "$FRONTEND" && npm run build)

log "Checking API smoke endpoints..."
(cd "$BACKEND" && python - <<'PY'
import json
from fastapi.testclient import TestClient
from hc_analytics.api.app import app

client = TestClient(app)
health = client.get("/health")
meta = client.get("/api/meta")
assert health.status_code == 200, health.text
assert meta.status_code == 200, meta.text
print(json.dumps(meta.json(), indent=2))
PY
)

log "Verification passed."

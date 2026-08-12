#!/usr/bin/env bash
# Idempotent environment setup: Python venv, pinned deps, Node/npm, .env
set -euo pipefail

# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

log "MedAstraX setup (repo: $ROOT)"

ensure_env_file
install_backend_deps
install_frontend_deps

# macOS: make XGBoost find OpenMP without requiring Homebrew sudo installs.
if [[ "$(uname -s)" == "Darwin" ]]; then
  if [[ -x "$ROOT/scripts/ensure_xgboost_libomp.sh" ]]; then
    "$ROOT/scripts/ensure_xgboost_libomp.sh" || log "Warning: could not link XGBoost libomp (optional on Linux/CI)."
  fi
fi

log "Setup complete."
echo ""
echo "Next steps:"
echo "  ./scripts/verify.sh          # run tests and smoke checks"
echo "  ./scripts/start-dashboard.sh # API + dashboard"
echo ""
echo "After staging CMS files in data/raw/:"
echo "  source backend/.venv/bin/activate"
echo "  python -m hc_analytics.ingestion"
echo "  python -m hc_analytics.features"
echo "  python -m hc_analytics.modeling"
echo "  python -m hc_analytics.explainability --study-cases-only"
echo "  python scripts/generate_study_cases.py"
echo "  python scripts/generate_frozen_summaries.py"

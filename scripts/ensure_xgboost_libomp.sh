#!/usr/bin/env bash
# Ensure XGBoost can load OpenMP on macOS without a system Homebrew libomp.
# Prefer sklearn's bundled libomp.dylib and rewrite libxgboost's dependency
# to @loader_path so SHAP/numba are not broken by DYLD_LIBRARY_PATH hacks.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${ROOT}/backend/.venv"
SITE="${VENV}/lib"
PYVER="$(ls "${SITE}" | grep -E '^python' | head -1 || true)"
if [[ -z "${PYVER}" ]]; then
  echo "No backend venv found at ${VENV}. Run ./scripts/setup.sh first." >&2
  exit 1
fi
LIBOMP="${SITE}/${PYVER}/site-packages/sklearn/.dylibs/libomp.dylib"
XGBLIB="${SITE}/${PYVER}/site-packages/xgboost/lib"
XGB="${XGBLIB}/libxgboost.dylib"
if [[ ! -f "${LIBOMP}" ]]; then
  echo "Missing sklearn libomp at ${LIBOMP}" >&2
  exit 1
fi
if [[ ! -f "${XGB}" ]]; then
  echo "Missing XGBoost dylib at ${XGB}" >&2
  exit 1
fi
ln -sfn "${LIBOMP}" "${XGBLIB}/libomp.dylib"
if command -v install_name_tool >/dev/null 2>&1; then
  install_name_tool -change "@rpath/libomp.dylib" "@loader_path/libomp.dylib" "${XGB}" || true
  if command -v codesign >/dev/null 2>&1; then
    codesign --force --sign - "${XGB}" >/dev/null 2>&1 || true
  fi
fi
echo "Linked ${XGBLIB}/libomp.dylib -> ${LIBOMP}"

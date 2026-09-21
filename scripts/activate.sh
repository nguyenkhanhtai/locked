#!/usr/bin/env bash

# ------------------------------------------------------------
# activate.sh
# ------------------------------------------------------------
# Activates the Python virtual environment and launches Locked
# ------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_PATH="${PROJECT_ROOT}/.venv"

# Activate virtual environment
if [[ -f "${VENV_PATH}/bin/activate" ]]; then
  source "${VENV_PATH}/bin/activate"
elif [[ -f "${VENV_PATH}/Scripts/activate" ]]; then
  source "${VENV_PATH}/Scripts/activate"
else
  echo "❌ Virtual environment activation script not found in ${VENV_PATH}."
  exit 1
fi

echo "✅ Virtual environment activated."

RUN_PATH="${PROJECT_ROOT}/backend/run.py"
if [[ -f "${RUN_PATH}" ]]; then
  exec python3 "${RUN_PATH}"
else
  echo "⚠️ run.py not found at ${RUN_PATH}."
fi

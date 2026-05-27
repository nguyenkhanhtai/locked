#!/usr/bin/env bash

# ------------------------------------------------------------
# activate.sh
# ------------------------------------------------------------
# This script is intended for Linux/macOS environments.
# It activates the project's Python virtual environment located
# in the .venv directory (relative to the project root) and
# launches the backend server (app.py).
#
# Usage:
#   source scripts/activate.sh   # to keep the venv active in the current shell
#   OR
#   ./scripts/activate.sh        # will activate, start server, and keep it running
# ------------------------------------------------------------

# Resolve the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_PATH="${PROJECT_ROOT}/.venv"

# Activate virtual environment
if [[ -f "${VENV_PATH}/bin/activate" ]]; then
  # Standard venv layout for Linux/macOS
  source "${VENV_PATH}/bin/activate"
elif [[ -f "${VENV_PATH}/Scripts/activate" ]]; then
  # Fallback for venv created on Windows but used on WSL/Unix
  source "${VENV_PATH}/Scripts/activate"
else
  echo "❌ Virtual environment activation script not found in ${VENV_PATH}."
  exit 1
fi

echo "✅ Virtual environment activated."

# Start the backend server (app.py) if it exists
APP_PATH="${PROJECT_ROOT}/backend/app.py"
if [[ -f "${APP_PATH}" ]]; then
  echo "🚀 Starting backend server (app.py)..."
  # Run in the background and capture its PID
  python3 "${APP_PATH}" &
  SERVER_PID=$!
  echo "🟢 Backend server started with PID $SERVER_PID."
  # Start observer server if present
  OBSERVER_PATH="${PROJECT_ROOT}/backend/observer.py"
  if [[ -f "${OBSERVER_PATH}" ]]; then
    echo "🚀 Starting observer server (observer.py)..."
    python3 "${OBSERVER_PATH}" &
    OBSERVER_PID=$!
    echo "🟢 Observer server started with PID $OBSERVER_PID."
  else
    echo "⚠️ observer.py not found at ${OBSERVER_PATH}. No observer started."
  fi
  # Wait for both processes to finish
  wait $SERVER_PID $OBSERVER_PID
else
  echo "⚠️ app.py not found at ${APP_PATH}. No server started."
fi

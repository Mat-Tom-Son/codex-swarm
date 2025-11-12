#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="src:${PYTHONPATH:-}"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"

"$PYTHON_BIN" -m uvicorn app.api.main:app --reload --port 5050 --app-dir src &
API_PID=$!

"$PYTHON_BIN" -m uvicorn app.runner.main:app --reload --port 5055 --app-dir src &
RUNNER_PID=$!

trap "kill $API_PID $RUNNER_PID" INT TERM
wait

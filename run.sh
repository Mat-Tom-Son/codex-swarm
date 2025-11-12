#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3.11}"

if [ $# -lt 1 ]; then
  echo "Usage: ./run.sh <module> [args...]" >&2
  exit 1
fi

MODULE="$1"
shift

case "$MODULE" in
  crossrun)
    exec "${PYTHON_BIN}" -m scripts.crossrun "$@"
    ;;
  *)
    echo "Unknown module: $MODULE" >&2
    exit 1
    ;;
esac

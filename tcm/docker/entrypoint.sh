#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 0 ]]; then
  exec "$@"
fi

MODE="${TCM_APP_MODE:-production}"
MODE_LOWER="${MODE,,}"
APP_IMPORT="${TCM_APP_IMPORT_PATH:-tcm.app.main:app}"
HOST="${UVICORN_HOST:-0.0.0.0}"
PORT="${UVICORN_PORT:-8000}"
LOG_LEVEL="${UVICORN_LOG_LEVEL:-info}"

case "${MODE_LOWER}" in
  production)
    echo "[entrypoint] Starting TCM app in production mode" >&2
    exec uvicorn "${APP_IMPORT}" \
      --host "${HOST}" \
      --port "${PORT}" \
      --log-level "${LOG_LEVEL}" \
      --lifespan off
    ;;
  development)
    echo "[entrypoint] Starting TCM app in development mode (auto-reload enabled)" >&2
    exec uvicorn "${APP_IMPORT}" \
      --host "${HOST}" \
      --port "${PORT}" \
      --log-level "${LOG_LEVEL}" \
      --reload \
      --reload-dir /opt/tcm/tcm
    ;;
  *)
    echo "[entrypoint] Unsupported TCM_APP_MODE='${MODE}'. Allowed values: production, development" >&2
    exit 64
    ;;
esac

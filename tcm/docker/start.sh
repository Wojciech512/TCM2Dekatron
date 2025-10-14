#!/usr/bin/env sh
set -e
APP="tcm.app.main:app"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
PYTHON_BIN="${PYTHON_BIN:-python}"

if [ "$TCM_APP_MODE" = "development" ]; then
  exec "$PYTHON_BIN" -m uvicorn "$APP" --host "$HOST" --port "$PORT" --reload --log-level "${UVICORN_LOG_LEVEL:-debug}"
else
  exec "$PYTHON_BIN" -m gunicorn "$APP" \
    -k uvicorn.workers.UvicornWorker \
    --bind "$HOST:$PORT" \
    --workers "${WORKERS:-1}" \
    --timeout 60 \
    --access-logfile - --error-logfile - --log-level info
fi

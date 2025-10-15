#!/usr/bin/env sh
set -e
APP="tcm.app.main:app"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
PYTHON_BIN="${PYTHON_BIN:-python}"
DEFAULT_LOG_LEVEL="${UVICORN_LOG_LEVEL:-warning}"
export UVICORN_LOG_LEVEL="${UVICORN_LOG_LEVEL:-${DEFAULT_LOG_LEVEL}}"
export TCM_LOG_LEVEL="${TCM_LOG_LEVEL:-warning}"
export LOG_LEVEL="${LOG_LEVEL:-${TCM_LOG_LEVEL}}"

if [ "$TCM_APP_MODE" = "development" ]; then
  exec "$PYTHON_BIN" -m uvicorn "$APP" --host "$HOST" --port "$PORT" --reload --log-level "${UVICORN_LOG_LEVEL}"
else
  exec "$PYTHON_BIN" -m gunicorn "$APP" \
    -k uvicorn.workers.UvicornWorker \
    --bind "$HOST:$PORT" \
    --workers "${WORKERS:-1}" \
    --worker-tmp-dir "${WORKER_TMP_DIR:-/dev/shm}" \
    --timeout "${WORKER_TIMEOUT:-30}" \
    --graceful-timeout "${WORKER_GRACEFUL_TIMEOUT:-30}" \
    --keep-alive "${WORKER_KEEPALIVE:-5}" \
    --access-logfile /dev/null \
    --error-logfile - \
    --log-level "${GUNICORN_LOG_LEVEL:-warning}"
fi

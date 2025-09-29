# syntax=docker/dockerfile:1.6
FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOME=/opt/tcm

WORKDIR ${APP_HOME}

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
        libssl-dev \
        libsqlite3-mod-spatialite \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt constraints.txt ./
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt -c constraints.txt

COPY tcm/ ./tcm/

RUN useradd --create-home --uid 1000 --shell /bin/bash tcm \
    && chown -R tcm:tcm ${APP_HOME} \
    && install -d -o tcm -g tcm /var/lib/tcm

ENV TCM_DB_DIR=/var/lib/tcm

USER tcm

ENV UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${UVICORN_PORT}/health || exit 1

CMD ["uvicorn","tcm.app.main:app","--host","0.0.0.0","--port","8000","--log-level","debug","--lifespan","off"]
#CMD ["uvicorn","tcm.app.main:app","--host","0.0.0.0","--port","8000"]

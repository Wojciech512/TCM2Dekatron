# syntax=docker/dockerfile:1.6
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/opt/tcm \
    PIP_ROOT=/opt/python

WORKDIR ${APP_HOME}

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
        libssl-dev \
        libsqlite3-mod-spatialite \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt constraints.txt ./
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefix="${PIP_ROOT}" -r requirements.txt -c constraints.txt

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/opt/tcm \
    TCM_DB_DIR=/var/lib/tcm

WORKDIR ${APP_HOME}

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libsqlite3-mod-spatialite \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/python/ /usr/local/
COPY tcm/ ./tcm/
COPY tcm/docker/start.sh ./docker/start.sh

RUN addgroup --system tcm && adduser --system --ingroup tcm tcm \
    && chown -R tcm:tcm ${APP_HOME} \
    && install -d -o tcm -g tcm /var/lib/tcm \
    && chmod +x ./docker/start.sh

USER tcm

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/opt/tcm/docker/start.sh"]

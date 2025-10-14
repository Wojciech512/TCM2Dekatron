# syntax=docker/dockerfile:1.6
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/opt/tcm

WORKDIR ${APP_HOME}

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
        libssl-dev \
        libsqlite3-mod-spatialite \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt constraints.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt -c constraints.txt

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/opt/tcm \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000

WORKDIR ${APP_HOME}

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libsqlite3-mod-spatialite \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
COPY tcm/ ./tcm/
COPY tcm/docker/start.sh ./docker/start.sh

RUN chmod +x /opt/tcm/docker/start.sh \
    && groupadd --system tcm \
    && useradd --system --gid tcm --no-create-home --home ${APP_HOME} --shell /usr/sbin/nologin tcm \
    && mkdir -p /var/lib/tcm \
    && chown -R tcm:tcm /var/lib/tcm ${APP_HOME}

ENV TCM_DB_DIR=/var/lib/tcm

USER tcm

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

ENTRYPOINT ["/opt/tcm/docker/start.sh"]

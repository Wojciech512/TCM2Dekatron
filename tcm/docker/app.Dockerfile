# syntax=docker/dockerfile:1.6
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/opt/tcm \
    PATH="/opt/python/usr/local/bin:${PATH}"

WORKDIR ${APP_HOME}

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
        libssl-dev \
        libsqlite3-mod-spatialite \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt constraints.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir --prefix="/opt/python" -r requirements.txt -c constraints.txt

FROM node:20-alpine AS assets

WORKDIR /build

COPY package.json package-lock.json tsconfig.json ./
RUN npm ci

COPY tcm/app/static/ts ./tcm/app/static/ts
RUN npm run build:ts

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
COPY --from=assets /build/tcm/app/static/js ./tcm/app/static/js
COPY tcm/docker/start.sh ./docker/start.sh

RUN addgroup --system tcm && adduser --system --ingroup tcm tcm \
    && chown -R tcm:tcm ${APP_HOME} \
    && install -d -o tcm -g tcm /var/lib/tcm \
    && chmod +x ./docker/start.sh

USER tcm

EXPOSE 8000

ENTRYPOINT ["/opt/tcm/docker/start.sh"]

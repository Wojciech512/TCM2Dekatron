# syntax=docker/dockerfile:1.6
FROM nginx:1.25-alpine

ARG UID=1000
ARG GID=1000

RUN addgroup -g ${GID} tcm \
    && adduser -D -G tcm -u ${UID} tcm

COPY tcm/deploy/reverse-proxy/nginx.conf /etc/nginx/nginx.conf
COPY tcm/deploy/reverse-proxy/conf.d/ /etc/nginx/conf.d/
COPY tcm/deploy/reverse-proxy/certs/ /etc/nginx/certs/

USER tcm

EXPOSE 8443

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider https://127.0.0.1:8443/health || exit 1

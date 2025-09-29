FROM nginx:1.25-alpine

COPY tcm/deploy/reverse-proxy/nginx.conf /etc/nginx/nginx.conf
COPY tcm/deploy/reverse-proxy/conf.d/ /etc/nginx/conf.d/
COPY tcm/deploy/reverse-proxy/certs/ /etc/nginx/certs/

EXPOSE 8443
#HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
#  CMD wget --no-verbose --no-check-certificate --tries=1 --spider http://localhost:8443/health || exit 1

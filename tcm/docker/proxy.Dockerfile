FROM nginx:1.25-alpine

COPY tcm/deploy/reverse-proxy/nginx.conf /etc/nginx/nginx.conf
COPY tcm/deploy/reverse-proxy/conf.d/ /etc/nginx/conf.d/
COPY tcm/deploy/reverse-proxy/certs/ /etc/nginx/certs/

EXPOSE 8443
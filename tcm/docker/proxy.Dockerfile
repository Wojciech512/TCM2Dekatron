# syntax=docker/dockerfile:1.6
FROM node:20-alpine AS assets

ENV NODE_ENV=production
WORKDIR /build

COPY package.json package-lock.json tsconfig.json ./
RUN npm ci --ignore-scripts \
    && npm cache clean --force

COPY tcm/app/static/ts ./tcm/app/static/ts
RUN npm run build:ts

FROM nginx:1.25-alpine

RUN rm -f /etc/nginx/conf.d/default.conf \
    && mkdir -p /var/www/static \
    && chown -R nginx:nginx /var/www/static

COPY --from=assets /build/tcm/app/static/js /var/www/static/js
COPY tcm/app/static/style.css /var/www/static/style.css
COPY tcm/app/static/fonts /var/www/static/fonts
COPY tcm/deploy/reverse-proxy/nginx.conf /etc/nginx/nginx.conf
COPY tcm/deploy/reverse-proxy/conf.d/ /etc/nginx/conf.d/
COPY tcm/deploy/reverse-proxy/certs/ /etc/nginx/certs/

EXPOSE 8443

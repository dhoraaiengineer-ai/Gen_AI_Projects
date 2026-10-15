# MedInfo Assistant - frontend image: static UI (no build step) served by unprivileged nginx, which also
# reverse-proxies /api/ to the backend so the UI and API share one origin (strict CSP, no CORS).
# Runs as non-root uid 10001 with a read-only root filesystem (only /tmp is writable).
FROM nginxinc/nginx-unprivileged:1.27-alpine

USER root
# Alpine security updates; drop the stock site config (ours comes from the template below).
RUN apk upgrade --no-cache \
 && rm -f /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/nginx.conf
COPY default.conf.template /etc/nginx/templates/default.conf.template
COPY src/ /usr/share/nginx/html/
RUN chmod -R a+rX /usr/share/nginx/html /etc/nginx

# The image entrypoint renders templates with envsubst (only the variables below are substituted)
# into /tmp, which is the only writable path.
ENV NGINX_ENVSUBST_OUTPUT_DIR=/tmp \
    BACKEND_UPSTREAM=backend:8000 \
    SUPABASE_URL=https://example.supabase.co

USER 10001:10001
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/frontend-healthz >/dev/null || exit 1

#!/bin/sh
# Container entrypoint. `exec` makes uvicorn PID 1 so it receives SIGTERM from Docker/Kubernetes
# and shuts down gracefully (finishing in-flight requests, closing DB connections).
set -eu

# Keep WEB_CONCURRENCY=1 per container and scale with replicas: prometheus_client keeps metrics
# per process, so multiple workers in one container would report inconsistent numbers.
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-1}" \
  --timeout-keep-alive "${KEEP_ALIVE_SECONDS:-75}" \
  --timeout-graceful-shutdown "${GRACEFUL_SHUTDOWN_SECONDS:-25}" \
  --proxy-headers \
  --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}" \
  --no-access-log

# syntax=docker/dockerfile:1
# MedInfo Assistant - production image.
# Multi-stage, non-root (uid 10001), runs with a read-only root filesystem (only /tmp is writable,
# mounted as tmpfs/emptyDir), one uvicorn worker per container (scale with replicas).

############################ builder ############################
FROM python:3.11-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY requirements.txt /tmp/requirements.txt
# Packaging tools are removed after install: not needed at runtime and frequent CVE findings.
RUN pip install --upgrade pip \
 && pip install -r /tmp/requirements.txt \
 && pip uninstall -y setuptools wheel \
 && python -m pip uninstall -y pip \
 && find /opt/venv -name "__pycache__" -type d -prune -exec rm -rf {} +

############################ runtime ############################
FROM python:3.11-slim AS runtime
LABEL org.opencontainers.image.title="medinfo-assistant" \
      org.opencontainers.image.description="Safety-first medical information assistant (information only, not medical advice)"

# Debian security updates; OpenCV runtime libraries needed by RapidOCR; then drop the base image's
# pip/setuptools/wheel so they can't be used or flagged.
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*
# Separate step: an apt failure above must fail the build; only absent packages may be skipped here.
RUN (python -m pip uninstall -y setuptools wheel || true) \
 && (python -m pip uninstall -y pip || true) \
 && rm -rf /usr/local/lib/python3.11/ensurepip /usr/local/lib/python3.11/site-packages/pip*

RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=10001:10001 app /srv/app

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    APP_ENV=production \
    LOG_FORMAT=json \
    PORT=8000

WORKDIR /srv
USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status == 200 else 1)"]

# One worker per container; proxy headers from the load balancer.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--no-server-header"]

# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️
# FRONTEND DOCKERFILE v3.0
# Multi-stage build — Next.js 15 standalone output, non-root runtime.
#
# Build:  docker build -t autorag-client:<sha> ./autorag-client
# Run:    docker run -p 3000:3000 --env-file ../.env autorag-client:<sha>
#
# Rule 20: Next.js 15 App Router | Rule 70: non-root user | Rule 90: multi-stage build
#
# Required in next.config.js / next.config.ts:
#   output: 'standalone'   ← enables .next/standalone (smallest production image)

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — dependency installer
# Copies package manifests only so this layer is cache-hit on code-only changes.
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS deps

WORKDIR /app

# Copy package manifests only — cache-efficient
COPY package.json ./

# Regular install since this is a workspace package (lockfile managed at root)
RUN npm install --production=false
# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — builder
# Runs next build and produces the standalone output + static assets.
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Receive installed node_modules from deps stage
COPY --from=deps /app/node_modules ./node_modules

# Copy full source (respects .dockerignore — excludes node_modules, .next, .env*)
COPY . .

# Build-time env vars (non-secret NEXT_PUBLIC_* only — never inject secrets here)
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production
# Skip ESLint during Docker build to avoid module resolution issues
ENV ESLINT_NO_DEV_ERRORS=true
ENV NEXT_LINT_SKIP=true

RUN mkdir -p /app/public && npm run build


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 — production runner
# Only contains the standalone server bundle — no node_modules, no source.
# Requires `output: 'standalone'` in next.config.js|ts.
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS prod

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME="0.0.0.0"

# Non-root user — Rule 70: least-privilege runtime
RUN addgroup --system --gid 1001 nextjs \
    && adduser --system --uid 1001 nextjs

# Standalone bundle: self-contained server.js + minimal node_modules
COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
# Static assets (images, fonts, icons)
COPY --from=builder --chown=nextjs:nextjs /app/.next/static ./.next/static
# Public folder (favicons, manifest, robots.txt)
COPY --from=builder --chown=nextjs:nextjs /app/public ./public

USER nextjs

EXPOSE 3000

# Health check — Rule 85
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD wget -qO- http://localhost:3000/api/health || exit 1

# Standalone entry — Next.js generates server.js inside .next/standalone
CMD ["node", "server.js"]

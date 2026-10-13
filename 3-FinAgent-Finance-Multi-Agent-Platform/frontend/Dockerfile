# FinAgent UI image (Next.js standalone server on :3020). Build context = frontend/.
#   docker build -t finagent-frontend --build-arg SUPABASE_URL=... \
#     --build-arg SUPABASE_PUBLISHABLE_KEY=... frontend
# Only browser-safe values are build args (Supabase URL + *publishable* key, API mode). The API
# address is runtime-only (API_INTERNAL_URL, used by the same-origin proxy route).

ARG NODE_IMAGE=node:24-bookworm-slim

FROM ${NODE_IMAGE} AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund

FROM ${NODE_IMAGE} AS build
WORKDIR /app
ARG SUPABASE_URL=""
ARG SUPABASE_PUBLISHABLE_KEY=""
ARG NEXT_PUBLIC_API_MODE=proxy
ENV SUPABASE_URL=${SUPABASE_URL} \
    SUPABASE_PUBLISHABLE_KEY=${SUPABASE_PUBLISHABLE_KEY} \
    NEXT_PUBLIC_API_MODE=${NEXT_PUBLIC_API_MODE} \
    NEXT_OUTPUT=standalone \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN rm -rf .next && npm run build

FROM ${NODE_IMAGE} AS runtime
RUN groupadd --gid 10001 finagent && \
    useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin finagent
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3020 \
    HOSTNAME=0.0.0.0 \
    API_INTERNAL_URL=http://api:8020
COPY --from=build --chown=10001:10001 /app/.next/standalone ./
COPY --from=build --chown=10001:10001 /app/.next/static ./.next/static
COPY --from=build --chown=10001:10001 /app/public ./public
USER 10001:10001
EXPOSE 3020
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:3020/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server.js"]

# GenAI RAG Platform

A production-oriented RAG API: FastAPI + LangChain + LangGraph, with Supabase Postgres/pgvector for
retrieval and the EURI OpenAI-compatible gateway for chat and embeddings.

## Status

| Stage | Status |
|---|---|
| 1. Build and test locally | Done |
| 2. Dockerize | Done |
| 3. Push to GitHub | Committed locally; needs a remote |
| 4. GitHub Actions CI (`.github/workflows/ci.yml`) | Written; validated with actionlint |
| 5–6. Build image, push to ECR (`cd.yml`) | Written; validated with actionlint |
| 7. Terraform (`terraform/`) | Written; `terraform validate` passes; **not applied** |
| 8. Deploy to EKS (`k8s/`) | Manifests tested on a local kind cluster |
| 9–11. Prometheus, Grafana, alerts (`monitoring/`) | Tested locally with docker compose; on EKS via Terraform |

## Deployment target

| | |
|---|---|
| AWS region | `ap-northeast-1` (Tokyo): ECR, EKS and Terraform resources |
| Database | Supabase Postgres + pgvector, `ap-northeast-1`, via the transaction pooler (port 6543) |

The app and database share a region so each query avoids a cross-region round trip.

## Architecture

```
app/
├── main.py            FastAPI app factory, lifespan, error handlers, /metrics mount
├── config.py          Settings from env vars (secrets are SecretStr)
├── container.py       Composition root: wires providers -> retriever -> graphs -> service
├── api/               HTTP layer only: routes, health probes, dependencies
├── agents/            LangGraph graphs: rag_graph (retrieve -> generate), research_agent (tool loop)
├── rag/
│   ├── providers.py   ChatOpenAI / OpenAIEmbeddings (EURI) and PGVector factories
│   ├── retriever.py   Splitting, ingestion, similarity search
│   ├── service.py     Use cases the API calls: ingest, query, run_agent
│   └── prompts.py
├── core/              Logging (text/JSON) and Prometheus metrics
├── models/            Pydantic request/response schemas
└── static/            Chat UI (plain HTML/CSS/JS, no build step), served at /
```

Dependencies point inward: `api` → `rag/service` → `agents` + `retriever` → LangChain interfaces.
Only `rag/providers.py` and `container.py` know about EURI and Postgres, so tests swap in fakes.

## Authentication and authorization

Users sign in on the UI with Supabase Auth (email + password). Every API call carries the Supabase
access token, and the API verifies it against the project's public JWKS (ES256). No secret key is involved.

| Endpoint | Access |
|---|---|
| `/`, `/static/*`, `/health/*`, `/api/v1/auth/config` | Public |
| `POST /api/v1/query`, `POST /api/v1/agent`, `GET /api/v1/me` | Any signed-in user |
| `POST /api/v1/ingest` | `admin` only (ingested documents become answers for everyone) |
| `/metrics` | Public locally; restricted to in-cluster Prometheus in Stage 9 |

**Status codes:** a missing or invalid token gets 401. A signed-in user without the needed role gets 403.

**Making someone an admin:** run this in the Supabase SQL editor. The user then signs out and back in.

```sql
update auth.users
set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb) || '{"app_role": "admin"}'::jsonb
where email = 'someone@example.com';
```

`app_metadata` can only be changed server-side, so users can't promote themselves.

**Local development:** `AUTH_ENABLED=false` treats every caller as admin. The app refuses to start with
that setting when `ENVIRONMENT` is `staging` or `prod`.

## LLM fallbacks

| Mode | Primary | Fallback (on rate limit / quota / outage / provider error) |
|---|---|---|
| Quick answer (`/query`) | `LLM_MODEL` (gpt-4.1-nano) | `LLM_FALLBACK_MODEL` (gemini-2.0-flash) |
| Research (`/agent`) | `LLM_MODEL` | `AGENT_FALLBACK_MODEL` (gpt-4o-mini) |

The agent needs a separate fallback because Gemini via EURI fails on the turn after a tool call (HTTP 400):
Gemini expects its thought signature back, and LangChain's OpenAI client drops it. Every fallback is logged
as a warning and counted in `rag_llm_fallbacks_total{model=...}`. Responses report the model that actually
answered.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Chat UI: ask questions, see cited sources, add documents |
| GET | `/health/live` | Liveness: process is up (never checks dependencies) |
| GET | `/health/ready` | Readiness: database reachable; 503 otherwise |
| POST | `/api/v1/ingest` | Split, embed and store documents |
| POST | `/api/v1/query` | Single-pass RAG answer with cited sources |
| POST | `/api/v1/agent` | Multi-search research agent for multi-part questions |
| GET | `/metrics` | Prometheus metrics |
| GET | `/docs` | OpenAPI UI |

LLM failures map to clear statuses: provider rate limit or daily quota → 429, provider error → 502,
provider unreachable → 503.

## Run locally

Requires Python 3.11+ and Docker (for a local pgvector database).

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows; use .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt

cp .env.example .env              # then set EURI_API_KEY and DATABASE_URL

# Local pgvector (or point DATABASE_URL at Supabase instead)
docker run -d --name rag-pgvector -e POSTGRES_USER=rag -e POSTGRES_PASSWORD=rag \
  -e POSTGRES_DB=rag -p 5432:5432 pgvector/pgvector:pg16

uvicorn app.main:app --reload
```

Try it:

```bash
curl -X POST localhost:8000/api/v1/ingest -H "Content-Type: application/json" \
  -d '{"documents":[{"text":"Paris is the capital of France.","source":"geo.md"}]}'
curl -X POST localhost:8000/api/v1/query -H "Content-Type: application/json" \
  -d '{"question":"What is the capital of France?"}'
```

### Using Supabase

Set `DATABASE_URL` to the URI from Supabase → Project Settings → Database → Connection string.
`postgresql://` URLs are accepted as-is. On first start the app enables the `vector` extension and
creates the LangChain tables (`langchain_pg_collection`, `langchain_pg_embedding`).

## Run in Docker

```bash
docker compose up --build                     # app on :8000 against DATABASE_URL from .env (Supabase)
docker compose --profile local-db up --build  # also app-local on :8001 against a local pgvector
```

The image is multi-stage `python:3.11-slim` (about 550 MB unpacked). It runs as non-root uid 10001,
has no pip, and includes a Docker `HEALTHCHECK` on `/health/live`. It contains no secrets; compose
passes `.env` in at runtime. Compose also runs it with a read-only filesystem, all Linux capabilities
dropped, and `no-new-privileges`. Uvicorn is PID 1, so `SIGTERM` gives a graceful shutdown. Keep
`WEB_CONCURRENCY=1` and scale with replicas, because Prometheus metrics are per-process.

## Monitoring locally

```bash
docker compose --profile monitoring up -d   # Prometheus :9090, Grafana :3000 (admin / GRAFANA_ADMIN_PASSWORD from .env)
```

`monitoring/prometheus/alerts.yml` and `monitoring/grafana/dashboards/*.json` are the single source of
truth: the local stack mounts them, and Terraform loads the same files into kube-prometheus-stack on EKS.

## Deploying to AWS (first time)

**Cost:** roughly **$190–230/month** in ap-northeast-1. EKS control plane is about $73, two t3.large nodes
about $110, NAT gateway about $45 plus data, the ALB about $20, plus EBS. Run `terraform destroy` when you're done testing.

Prerequisites: an AWS account, the AWS CLI logged in (`aws sts get-caller-identity`), Terraform ≥ 1.6, and the repo on GitHub.

1. **Infrastructure**
   ```bash
   cd terraform
   cp terraform.tfvars.example terraform.tfvars   # set github_repo = "owner/name"
   terraform init
   terraform plan -out tf.plan                    # review: about 60-70 resources
   terraform apply tf.plan                        # about 20 minutes
   ```
2. **GitHub settings** (repo → Settings → Secrets and variables → Actions):
   - Variables: `AWS_REGION`, `AWS_ROLE_ARN`, `ECR_REPOSITORY`, `EKS_CLUSTER_NAME` (all from `terraform output`), and `SUPABASE_URL`.
   - Environment `production` → secrets: `EURI_API_KEY`, `DATABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`.
     Add required reviewers on the environment if you want a manual approval before each deploy.
3. **Deploy:** push to `main`. CI runs, then CD builds the image, pushes it to ECR and rolls it out.
   ```bash
   aws eks update-kubeconfig --name genai-rag-prod --region ap-northeast-1
   kubectl -n rag get ingress rag-api   # ADDRESS = public URL (HTTP until you add an ACM certificate)
   ```
4. **Grafana:** `kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80`, then
   log in as `admin` with the password from `terraform output -raw grafana_admin_password`.
   Alertmanager has no receivers yet. Add Slack or email in the kube-prometheus-stack values to get notified.

**Before real users:** add HTTPS (see `k8s/ingress.yaml`), restrict `cluster_endpoint_public_access_cidrs`,
and enable the S3 backend in `terraform/providers.tf`.

## Kubernetes locally (kind)

```bash
kind create cluster --name rag-local
kind load docker-image genai-rag-platform:local --name rag-local
kubectl create namespace rag
kubectl -n rag create secret generic rag-secrets --from-literal=EURI_API_KEY=... --from-literal=DATABASE_URL=...
kubectl kustomize docker/k8s-local | kubectl apply -f -   # replace the SUPABASE_* placeholders first
```

## Tests and lint

```bash
pytest          # offline: fake LLM, fake embeddings, in-memory vector store
ruff check . && ruff format --check .
```

## Configuration

All settings come from environment variables; see [.env.example](.env.example). Notes:

- `EMBEDDING_DIM` must match `EMBEDDING_MODEL`. Changing models needs a new `COLLECTION_NAME`.
- On EURI's free tier each model gets about 10,000 tokens per day. Expect 429s under real load.
- `LLM_MODEL` takes any chat model your EURI key can access (`GET {LLM_BASE_URL}/models`).

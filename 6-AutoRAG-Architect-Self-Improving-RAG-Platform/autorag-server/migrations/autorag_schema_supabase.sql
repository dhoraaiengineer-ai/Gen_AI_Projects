-- ============================================================
-- AutoRAG Architect — Full Schema Bootstrap SQL
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New Query)
-- Equivalent to: alembic upgrade head (migrations 0001 → 0004)
-- Generated: 08-Jun-2026
-- ============================================================


-- ── MIGRATION 0001: Extensions ───────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";


-- ── MIGRATION 0002: Core Tables ──────────────────────────────────────────────

-- 1. organizations
CREATE TABLE IF NOT EXISTS organizations (
    id              UUID        PRIMARY KEY NOT NULL,
    name            VARCHAR(255) NOT NULL,
    slug            VARCHAR(100) NOT NULL,
    plan            VARCHAR(50)  NOT NULL DEFAULT 'free',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    CONSTRAINT uq_organizations_name UNIQUE (name),
    CONSTRAINT uq_organizations_slug UNIQUE (slug)
);

-- 2. users
CREATE TABLE IF NOT EXISTS users (
    id              UUID        PRIMARY KEY NOT NULL,
    organization_id UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email           VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255),
    role            VARCHAR(50)  NOT NULL DEFAULT 'viewer',
    hashed_password VARCHAR(255),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    CONSTRAINT uq_users_org_email UNIQUE (organization_id, email),
    CONSTRAINT ck_users_role CHECK (role IN ('admin', 'viewer'))
);

-- 3. pipelines
CREATE TABLE IF NOT EXISTS pipelines (
    id              UUID         PRIMARY KEY NOT NULL,
    organization_id UUID         NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    status          VARCHAR(50)  NOT NULL DEFAULT 'pending',
    chunk_strategy  VARCHAR(100),
    embedding_model VARCHAR(255) NOT NULL DEFAULT 'gemini-embedding-2',
    config_yaml     TEXT,
    unified_score   NUMERIC(4,3),
    current_version INTEGER      NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    CONSTRAINT uq_pipelines_org_name UNIQUE (organization_id, name),
    CONSTRAINT ck_pipelines_status CHECK (status IN ('pending','running','ready','failed','decommissioned'))
);

-- 4. pipeline_versions
CREATE TABLE IF NOT EXISTS pipeline_versions (
    id                UUID         PRIMARY KEY NOT NULL,
    pipeline_id       UUID         NOT NULL REFERENCES pipelines(id) ON DELETE CASCADE,
    organization_id   UUID         NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    version_number    INTEGER      NOT NULL,
    vector_table_name VARCHAR(255) NOT NULL,
    chunk_strategy    VARCHAR(100) NOT NULL DEFAULT 'semantic',
    chunk_size        INTEGER,
    chunk_overlap     INTEGER,
    embedding_model   VARCHAR(255) NOT NULL DEFAULT 'gemini-embedding-2',
    retrieval_k       INTEGER,
    config_snapshot   JSONB,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_pipeline_versions_pipeline_version UNIQUE (pipeline_id, version_number),
    CONSTRAINT uq_pipeline_versions_vector_table     UNIQUE (vector_table_name)
);

-- 5. evaluation_runs
CREATE TABLE IF NOT EXISTS evaluation_runs (
    id                  UUID        PRIMARY KEY NOT NULL,
    pipeline_id         UUID        NOT NULL REFERENCES pipelines(id) ON DELETE CASCADE,
    organization_id     UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    run_id              UUID        NOT NULL,
    unified_score       NUMERIC(4,3),
    recall              NUMERIC(4,3),
    quality             NUMERIC(4,3),
    faithfulness        NUMERIC(4,3),
    latency_p95_ms      INTEGER,
    cost_usd            NUMERIC(10,6),
    adversarial_passed  BOOLEAN     NOT NULL DEFAULT FALSE,
    ragas_metrics       JSONB,
    failure_taxonomy    JSONB,
    status              VARCHAR(50) NOT NULL DEFAULT 'pending',
    dataset_version     VARCHAR(50),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_evaluation_runs_run_id             UNIQUE (run_id),
    CONSTRAINT ck_evaluation_runs_faithfulness_nonneg CHECK (faithfulness IS NULL OR faithfulness >= 0),
    CONSTRAINT ck_evaluation_runs_status             CHECK (status IN ('pending','running','completed','blocked'))
);

-- 6. retrieval_chunks
CREATE TABLE IF NOT EXISTS retrieval_chunks (
    id                  UUID        PRIMARY KEY NOT NULL,
    pipeline_version_id UUID        NOT NULL REFERENCES pipeline_versions(id) ON DELETE CASCADE,
    organization_id     UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    evaluation_run_id   UUID        REFERENCES evaluation_runs(id) ON DELETE SET NULL,
    source_uri          TEXT        NOT NULL,
    chunk_strategy      VARCHAR(100) NOT NULL,
    page_number         INTEGER,
    chunk_index         INTEGER     NOT NULL,
    content_hash        VARCHAR(64),
    parent_chunk_id     UUID        REFERENCES retrieval_chunks(id) ON DELETE SET NULL,
    token_count         INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. experiment_runs
CREATE TABLE IF NOT EXISTS experiment_runs (
    id                        UUID        PRIMARY KEY NOT NULL,
    pipeline_id               UUID        NOT NULL REFERENCES pipelines(id) ON DELETE CASCADE,
    organization_id           UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    parent_evaluation_run_id  UUID        REFERENCES evaluation_runs(id) ON DELETE SET NULL,
    result_pipeline_version_id UUID       REFERENCES pipeline_versions(id) ON DELETE SET NULL,
    mlflow_run_id             VARCHAR(255),
    variant_config            JSONB       NOT NULL,
    unified_score             NUMERIC(4,3),
    score_delta               NUMERIC(4,3),
    status                    VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_experiment_runs_status CHECK (status IN ('pending','running','completed','failed'))
);

-- 8. deployments
CREATE TABLE IF NOT EXISTS deployments (
    id                      UUID        PRIMARY KEY NOT NULL,
    pipeline_id             UUID        NOT NULL REFERENCES pipelines(id) ON DELETE CASCADE,
    evaluation_run_id       UUID        NOT NULL REFERENCES evaluation_runs(id),
    organization_id         UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    task_arn                VARCHAR(500) NOT NULL,
    rollback_task_arn       VARCHAR(500),
    status                  VARCHAR(50) NOT NULL DEFAULT 'pending',
    unified_score_at_deploy NUMERIC(4,3),
    deployed_at             TIMESTAMPTZ,
    promoted_at             TIMESTAMPTZ,
    rolled_back_at          TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_deployments_status CHECK (status IN ('pending','blue_green','promoted','rolled_back','failed'))
);

-- 9. audit_log (INSERT ONLY — trigger enforced below)
CREATE TABLE IF NOT EXISTS audit_log (
    id              UUID        PRIMARY KEY NOT NULL,
    event_type      VARCHAR(100) NOT NULL,
    run_id          UUID,
    organization_id UUID,
    payload         JSONB       NOT NULL,
    trace_id        VARCHAR(255),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_audit_log_event_type CHECK (
        event_type IN (
            'pipeline_created','pipeline_updated',
            'ingest_started','ingest_completed',
            'eval_started','eval_completed',
            'deploy_started','deploy_completed',
            'rollback_triggered','hitl_approved','hitl_rejected','cost_limit_exceeded'
        )
    )
);


-- ── MIGRATION 0003: Indexes ───────────────────────────────────────────────────

-- organizations
CREATE INDEX IF NOT EXISTS ix_organizations_slug       ON organizations (slug);
CREATE INDEX IF NOT EXISTS ix_organizations_deleted_at ON organizations (deleted_at);

-- users
CREATE INDEX IF NOT EXISTS ix_users_organization_id ON users (organization_id);
CREATE INDEX IF NOT EXISTS ix_users_email           ON users (email);
CREATE INDEX IF NOT EXISTS ix_users_deleted_at      ON users (deleted_at);
CREATE INDEX IF NOT EXISTS ix_users_org_email       ON users (organization_id, email);

-- pipelines
CREATE INDEX IF NOT EXISTS ix_pipelines_organization_id ON pipelines (organization_id);
CREATE INDEX IF NOT EXISTS ix_pipelines_status          ON pipelines (status);
CREATE INDEX IF NOT EXISTS ix_pipelines_deleted_at      ON pipelines (deleted_at);
CREATE INDEX IF NOT EXISTS ix_pipelines_created_at      ON pipelines (created_at);
CREATE INDEX IF NOT EXISTS ix_pipelines_org_status      ON pipelines (organization_id, status);

-- pipeline_versions
CREATE INDEX IF NOT EXISTS ix_pipeline_versions_pipeline_id     ON pipeline_versions (pipeline_id);
CREATE INDEX IF NOT EXISTS ix_pipeline_versions_organization_id ON pipeline_versions (organization_id);
CREATE INDEX IF NOT EXISTS ix_pipeline_versions_created_at      ON pipeline_versions (created_at);

-- evaluation_runs
CREATE UNIQUE INDEX IF NOT EXISTS ix_evaluation_runs_run_id         ON evaluation_runs (run_id);
CREATE INDEX IF NOT EXISTS ix_evaluation_runs_pipeline_id           ON evaluation_runs (pipeline_id);
CREATE INDEX IF NOT EXISTS ix_evaluation_runs_organization_id       ON evaluation_runs (organization_id);
CREATE INDEX IF NOT EXISTS ix_evaluation_runs_status                ON evaluation_runs (status);
CREATE INDEX IF NOT EXISTS ix_evaluation_runs_created_at            ON evaluation_runs (created_at);
CREATE INDEX IF NOT EXISTS ix_evaluation_runs_org_pipeline          ON evaluation_runs (organization_id, pipeline_id);
CREATE INDEX IF NOT EXISTS ix_evaluation_runs_ragas_metrics_gin     ON evaluation_runs USING gin (ragas_metrics);
CREATE INDEX IF NOT EXISTS ix_evaluation_runs_failure_taxonomy_gin  ON evaluation_runs USING gin (failure_taxonomy);

-- retrieval_chunks
CREATE INDEX IF NOT EXISTS ix_retrieval_chunks_pipeline_version_id ON retrieval_chunks (pipeline_version_id);
CREATE INDEX IF NOT EXISTS ix_retrieval_chunks_organization_id     ON retrieval_chunks (organization_id);
CREATE INDEX IF NOT EXISTS ix_retrieval_chunks_evaluation_run_id   ON retrieval_chunks (evaluation_run_id);
CREATE INDEX IF NOT EXISTS ix_retrieval_chunks_source_uri          ON retrieval_chunks (source_uri);
CREATE INDEX IF NOT EXISTS ix_retrieval_chunks_chunk_strategy      ON retrieval_chunks (chunk_strategy);
CREATE INDEX IF NOT EXISTS ix_retrieval_chunks_parent_chunk_id     ON retrieval_chunks (parent_chunk_id);
CREATE INDEX IF NOT EXISTS ix_retrieval_chunks_created_at          ON retrieval_chunks (created_at);

-- experiment_runs
CREATE INDEX IF NOT EXISTS ix_experiment_runs_pipeline_id                  ON experiment_runs (pipeline_id);
CREATE INDEX IF NOT EXISTS ix_experiment_runs_organization_id              ON experiment_runs (organization_id);
CREATE INDEX IF NOT EXISTS ix_experiment_runs_parent_evaluation_run_id     ON experiment_runs (parent_evaluation_run_id);
CREATE INDEX IF NOT EXISTS ix_experiment_runs_status                       ON experiment_runs (status);
CREATE INDEX IF NOT EXISTS ix_experiment_runs_created_at                   ON experiment_runs (created_at);
CREATE INDEX IF NOT EXISTS ix_experiment_runs_variant_config_gin           ON experiment_runs USING gin (variant_config);

-- deployments
CREATE INDEX IF NOT EXISTS ix_deployments_pipeline_id       ON deployments (pipeline_id);
CREATE INDEX IF NOT EXISTS ix_deployments_organization_id   ON deployments (organization_id);
CREATE INDEX IF NOT EXISTS ix_deployments_evaluation_run_id ON deployments (evaluation_run_id);
CREATE INDEX IF NOT EXISTS ix_deployments_status            ON deployments (status);
CREATE INDEX IF NOT EXISTS ix_deployments_created_at        ON deployments (created_at);
CREATE INDEX IF NOT EXISTS ix_deployments_org_pipeline      ON deployments (organization_id, pipeline_id);

-- audit_log
CREATE INDEX IF NOT EXISTS ix_audit_log_organization_id ON audit_log (organization_id);
CREATE INDEX IF NOT EXISTS ix_audit_log_event_type      ON audit_log (event_type);
CREATE INDEX IF NOT EXISTS ix_audit_log_run_id          ON audit_log (run_id);
CREATE INDEX IF NOT EXISTS ix_audit_log_created_at      ON audit_log (created_at);
CREATE INDEX IF NOT EXISTS ix_audit_log_payload_gin     ON audit_log USING gin (payload);
CREATE INDEX IF NOT EXISTS ix_audit_log_org_event_type  ON audit_log (organization_id, event_type);


-- ── MIGRATION 0004: audit_log INSERT-ONLY Trigger ────────────────────────────

CREATE OR REPLACE FUNCTION block_audit_log_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'audit_log is INSERT ONLY — UPDATE and DELETE are permanently prohibited. Attempted operation: % on row id=%',
        TG_OP,
        COALESCE(OLD.id::text, 'unknown')
        USING ERRCODE = 'P0001';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_audit_log_block_update ON audit_log;
CREATE TRIGGER trg_audit_log_block_update
BEFORE UPDATE ON audit_log
FOR EACH ROW EXECUTE FUNCTION block_audit_log_mutation();

DROP TRIGGER IF EXISTS trg_audit_log_block_delete ON audit_log;
CREATE TRIGGER trg_audit_log_block_delete
BEFORE DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION block_audit_log_mutation();


-- ── DONE ─────────────────────────────────────────────────────────────────────
-- Tables created: organizations, users, pipelines, pipeline_versions,
--                 evaluation_runs, retrieval_chunks, experiment_runs,
--                 deployments, audit_log
-- Extensions: pgcrypto, vector
-- Triggers: audit_log UPDATE/DELETE blocked

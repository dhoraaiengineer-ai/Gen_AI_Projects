"""Business logic for pipeline lifecycle -- create, retrieve, version.

Architecture: routes -> PipelineService -> PipelineRepository (no skip-layer).
All business rules live here; repositories handle only persistence.

Rule 10: thin routes -- all orchestration lives in this service.
Rule 30: UUID v7 PKs, org-scoped queries, soft-delete pattern.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PipelineNameExistsError, PipelineNotFoundError
from app.models.pipeline import Pipeline
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.evaluation_repository import EvaluationRepository
from app.repositories.experiment_run_repository import ExperimentRunRepository
from app.repositories.pipeline_repository import PipelineRepository
from app.repositories.pipeline_version_repository import PipelineVersionRepository
from app.services.base import BaseService

logger = structlog.get_logger(__name__)


class PipelineService(BaseService):
    """Orchestrates pipeline creation and versioning. Called by routes/pipelines.py."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self._repo = PipelineRepository(db)
        self._version_repo = PipelineVersionRepository(db)
        self._experiment_repo = ExperimentRunRepository(db)
        self._eval_repo = EvaluationRepository(db)
        self._audit = AuditLogRepository(db)

    async def create(
        self,
        *,
        name: str,
        config_yaml: str | None,
        organization_id: str,
        x_trace_id: str,
        chunk_strategy: str | None = None,
        embedding_model: str = "gemini-embedding-2",
        status: str | None = None,
        variant_config: dict | None = None,
    ) -> dict:
        """Create a new pipeline row and log a pipeline_created audit event.

        Args:
            name: Human-readable pipeline name (unique per org).
            config_yaml: YAML from /configurator step 6 -- optional on creation.
            organization_id: Tenant UUID string -- mandatory.
            x_trace_id: Request correlation ID (propagated from API header).
            chunk_strategy: semantic | hierarchical | late -- optional.
            embedding_model: Must be gemini-embedding-2 (768-dim frozen contract).
            status: Only 'draft' is ever passed here (schema-enforced) -- the
                Configurator wizard creates the pipeline in 'draft' right after
                step 1. Omitted, the column's own server_default ('pending')
                applies, preserving prior behavior for any other caller.
            variant_config: Structured retrieval/chunking/generation settings
                from the Configurator wizard (chunk_size, chunk_overlap,
                retrieval_mode, top_k, reranker_enabled, llm_provider,
                temperature, max_tokens) -- 25-Jul-2026 fix. Previously these
                were only ever baked into the write-only config_yaml blob and
                never reached v1's config_snapshot, so get_active_config()
                (below) had nothing but chunk_strategy/embedding_model to seed
                GraphState.variant_config with at ingestion/retrieval/
                generation time -- every wizard setting past chunk_strategy
                was silently discarded. None of the fields here are fabricated
                defaults: they're exactly what the wizard's own Pydantic
                schema (ConfiguratorRequest, routes/configurator.py) declares
                and the user submitted.

        Returns:
            Dict representation of the created Pipeline.

        Raises:
            ValueError: If org_id is not a valid UUID or name already exists.
        """
        org_uuid = uuid.UUID(organization_id)

        extra_kwargs = {"status": status} if status is not None else {}
        try:
            pipeline = await self._repo.create(
                organization_id=org_uuid,
                name=name,
                config_yaml=config_yaml,
                chunk_strategy=chunk_strategy,
                embedding_model=embedding_model,
                **extra_kwargs,
            )
        except IntegrityError as exc:
            # 26-Jul-2026 fix: uq_pipelines_org_name violations previously
            # propagated as an unhandled IntegrityError, crashing the request
            # before any HTTP response was sent -- the browser saw a bare
            # "Failed to fetch" with no actionable detail. Roll back so the
            # session stays usable, then raise a clean domain error the route
            # can turn into a real {"status":"error",...} response.
            await self.db.rollback()
            if "uq_pipelines_org_name" in str(exc.orig):
                raise PipelineNameExistsError(name) from exc
            raise

        # 20-Jul-2026 fix: no pipeline_versions row was ever inserted at
        # creation time, so a freshly created pipeline had current_version=1
        # (the column's server_default) but zero matching version history --
        # a real gap for version listing / active-config resolution. Every
        # pipeline now has a real v1 row from the start, config_snapshot
        # reflecting exactly what was passed at creation (no fabricated
        # retrieval params -- those simply aren't set until an apply-
        # improvement flow supplies them).
        #
        # Version 4 (20-Jul-2026): vector_table_name previously encoded a
        # per-version physical table name that migration 0016 proved was
        # never actually reachable (every real dispatch used the same
        # hardcoded "v1.0" regardless of this value). All chunks now live in
        # the single shared pipeline_chunks table, partitioned by the
        # pipeline_version column -- this column now records that real
        # partition label instead of a fictitious table name. Must include
        # pipeline.id: the column's UNIQUE constraint is global (not scoped
        # per pipeline), and "pipeline_chunks:v1" alone would collide across
        # every pipeline's first version (live-confirmed via a real
        # integration test failure, UniqueViolationError on
        # uq_pipeline_versions_vector_table).
        vector_table_name = f"pipeline_chunks:{pipeline.id}:v1"
        config_snapshot: dict | None = None
        if chunk_strategy or variant_config:
            config_snapshot = {"chunk_strategy": chunk_strategy, "embedding_model": embedding_model}
            if variant_config:
                config_snapshot.update(variant_config)
        await self._version_repo.create(
            pipeline_id=pipeline.id,
            organization_id=org_uuid,
            version_number=1,
            vector_table_name=vector_table_name,
            chunk_strategy=chunk_strategy or "semantic",
            embedding_model=embedding_model,
            config_snapshot=config_snapshot,
        )

        await self._audit.insert(
            event_type="pipeline_created",
            organization_id=org_uuid,
            run_id=None,
            payload={
                "pipeline_id": str(pipeline.id),
                "name": name,
                "chunk_strategy": chunk_strategy,
                "embedding_model": embedding_model,
            },
            trace_id=x_trace_id,
        )

        await self.db.commit()

        logger.bind(
            pipeline_id=str(pipeline.id),
            org_id=organization_id,
            x_trace_id=x_trace_id,
        ).info("pipeline.created")

        return _pipeline_to_dict(pipeline)

    async def get_by_id(
        self,
        *,
        pipeline_id: str,
        organization_id: str,
    ) -> dict:
        """Fetch a pipeline by PK with org-scoping.

        Args:
            pipeline_id: UUID string of the pipeline.
            organization_id: Must match the pipeline's org (access control).

        Returns:
            Dict representation of the pipeline.

        Raises:
            PipelineNotFoundError: If pipeline is not found or deleted.
        """
        pipeline = await self._repo.get_by_id(
            pipeline_id=uuid.UUID(pipeline_id),
            organization_id=uuid.UUID(organization_id),
        )
        if pipeline is None:
            raise PipelineNotFoundError(
                f"Pipeline {pipeline_id} not found in org {organization_id}."
            )
        return _pipeline_to_dict(pipeline)

    async def finalize_draft(
        self,
        *,
        pipeline_id: str,
        organization_id: str,
        x_trace_id: str,
        chunk_strategy: str | None = None,
        variant_config: dict | None = None,
    ) -> dict:
        """Transition a pipeline out of 'draft' once the Configurator wizard
        completes (step 6, "Launch Pipeline"). The only status this ever
        writes is 'pending' -- enforced by PipelineFinalizeRequest's Literal
        type at the route layer, not re-checked here.

        Args:
            pipeline_id: Target pipeline UUID string.
            organization_id: Tenant UUID string -- access control.
            x_trace_id: Request correlation ID.
            chunk_strategy: Real value from wizard step 3, if it differs from
                what was set when the draft pipeline was created back at step
                1->2 (the draft is created before the user ever reaches step
                3, so this is often the first time the real choice is known).
            variant_config: Structured retrieval/chunking/generation settings
                collected across wizard steps 3-5 (25-Jul-2026 fix). v1's
                pipeline_versions row was already created back at step 1->2
                with only chunk_strategy/embedding_model -- pipeline_versions
                rows are immutable after creation by design (see
                PipelineVersionRepository's module docstring), so this can't
                retroactively edit v1. Instead, when either argument is real
                (non-None), this creates a real v2 via the same version-bump
                mechanism the apply-improvement/optimizer loop already uses
                (create_version(), see its own history-fix comment) and
                points current_version at it -- so get_active_config() (used
                by every real read path: ingestion.py/builder.py/query.py)
                resolves the pipeline's ACTUAL configured settings, not v1's
                near-empty snapshot.

        Returns:
            Dict representation of the updated pipeline.

        Raises:
            PipelineNotFoundError: If pipeline does not exist or is deleted.
        """
        org_uuid = uuid.UUID(organization_id)
        pip_uuid = uuid.UUID(pipeline_id)

        pipeline = await self._repo.get_by_id(pipeline_id=pip_uuid, organization_id=org_uuid)
        if pipeline is None:
            raise PipelineNotFoundError(
                f"Pipeline {pipeline_id} not found in org {organization_id}."
            )

        if chunk_strategy or variant_config:
            new_version = pipeline.current_version + 1
            vector_table_name = f"pipeline_chunks:{pipeline_id}:v{new_version}"
            resolved_chunk_strategy = chunk_strategy or pipeline.chunk_strategy or "semantic"

            config_snapshot: dict = {
                "chunk_strategy": resolved_chunk_strategy,
                "embedding_model": pipeline.embedding_model,
            }
            if variant_config:
                config_snapshot.update(variant_config)

            await self._repo.update_current_version(
                pipeline_id=pip_uuid,
                organization_id=org_uuid,
                current_version=new_version,
                chunk_strategy=chunk_strategy,
            )
            await self._version_repo.create(
                pipeline_id=pip_uuid,
                organization_id=org_uuid,
                version_number=new_version,
                vector_table_name=vector_table_name,
                chunk_strategy=resolved_chunk_strategy,
                embedding_model=pipeline.embedding_model,
                config_snapshot=config_snapshot,
            )

        await self._repo.update_status(
            pipeline_id=pip_uuid, organization_id=org_uuid, status="pending"
        )

        await self._audit.insert(
            event_type="pipeline_updated",
            organization_id=org_uuid,
            run_id=None,
            payload={"pipeline_id": pipeline_id, "status": "pending", "from_status": "draft"},
            trace_id=x_trace_id,
        )
        await self.db.commit()

        return await self.get_by_id(pipeline_id=pipeline_id, organization_id=organization_id)

    async def list_by_org(
        self,
        *,
        organization_id: str,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """List active pipelines for an org, each with its latest_run attached.

        Args:
            organization_id: Tenant filter -- mandatory.
            status: Optional status filter.
            limit: Page size (capped at 200 by this service).
            offset: Pagination offset.

        Returns:
            List of pipeline dicts ordered by created_at DESC. Each dict
            includes a `latest_run` key (same shape as GET /pipelines/{id}'s
            latest_run, or None) -- added 26-Jul-2026 so the frontend can stop
            fanning out one GET /pipelines/{id} per row (see
            EvaluationRepository.list_latest_by_pipeline_ids for why).
        """
        limit = min(limit, 200)
        org_uuid = uuid.UUID(organization_id)
        pipelines = await self._repo.list_by_org(
            organization_id=org_uuid,
            status=status,
            limit=limit,
            offset=offset,
        )
        latest_runs = await self._eval_repo.list_latest_by_pipeline_ids(
            pipeline_ids=[p.id for p in pipelines],
            organization_id=org_uuid,
        )
        results = []
        for p in pipelines:
            item = _pipeline_to_dict(p)
            run = latest_runs.get(p.id)
            item["latest_run"] = (
                {
                    "id": str(run.run_id),
                    "unified_score": float(run.unified_score) if run.unified_score is not None else None,
                    "faithfulness_score": float(run.faithfulness) if run.faithfulness is not None else None,
                    "status": run.status,
                    "finished_at": run.updated_at.isoformat() if run.status in ("completed", "blocked") else None,
                }
                if run is not None
                else None
            )
            results.append(item)
        return results

    async def create_version(
        self,
        *,
        pipeline_id: str,
        organization_id: str,
        config: dict,
        x_trace_id: str,
    ) -> dict:
        """Increment pipeline version and return version metadata.

        The new Supabase Vector table name follows the convention:
            autorag_{pipeline_id_no_hyphens}_{version_number}
        Table creation itself is deferred to the Builder Agent (D-12).

        Args:
            pipeline_id: Target pipeline UUID string.
            organization_id: Tenant UUID string.
            config: Hyperparameter dict for this version.
            x_trace_id: Request correlation ID.

        Returns:
            Dict with pipeline_id, version_number, and vector_table_name.

        Raises:
            PipelineNotFoundError: If pipeline does not exist or is deleted.
        """
        org_uuid = uuid.UUID(organization_id)
        pip_uuid = uuid.UUID(pipeline_id)

        pipeline = await self._repo.get_by_id(
            pipeline_id=pip_uuid,
            organization_id=org_uuid,
        )
        if pipeline is None:
            raise PipelineNotFoundError(
                f"Pipeline {pipeline_id} not found in org {organization_id}."
            )

        new_version = pipeline.current_version + 1
        # Version 4 (20-Jul-2026): see create()'s vector_table_name comment
        # above -- real partition label in the shared pipeline_chunks table,
        # not a fictitious per-version physical table name. Includes
        # pipeline_id since the column's UNIQUE constraint is global.
        vector_table_name = f"pipeline_chunks:{pipeline_id}:v{new_version}"

        # 20-Jul-2026 fix: this method previously computed new_version
        # locally but never persisted it -- a repeat call recomputed the
        # SAME version number, and neither `config` nor chunk_strategy/
        # embedding_model were ever written onto the pipeline row (only into
        # the audit log payload, which nothing reads back at runtime). Both
        # real bugs fixed together since Apply Improvement depends on
        # repeated, trustworthy version creation.
        new_chunk_strategy = config.get("chunk_strategy") if config else None
        new_embedding_model = config.get("embedding_model") if config else None

        await self._repo.update_current_version(
            pipeline_id=pip_uuid,
            organization_id=org_uuid,
            current_version=new_version,
            chunk_strategy=new_chunk_strategy,
            embedding_model=new_embedding_model,
        )
        await self._repo.update_status(
            pipeline_id=pip_uuid,
            organization_id=org_uuid,
            status="running",
        )

        new_version_row = await self._version_repo.create(
            pipeline_id=pip_uuid,
            organization_id=org_uuid,
            version_number=new_version,
            vector_table_name=vector_table_name,
            chunk_strategy=new_chunk_strategy or pipeline.chunk_strategy or "semantic",
            embedding_model=new_embedding_model or pipeline.embedding_model,
            chunk_size=config.get("chunk_size") if config else None,
            chunk_overlap=config.get("overlap") if config else None,
            retrieval_k=config.get("k_value") or config.get("top_k") if config else None,
            config_snapshot=config or None,
        )

        await self._audit.insert(
            event_type="pipeline_updated",
            organization_id=org_uuid,
            run_id=None,
            payload={
                "pipeline_id": pipeline_id,
                "new_version": new_version,
                "vector_table_name": vector_table_name,
                "config": config,
            },
            trace_id=x_trace_id,
        )

        await self.db.commit()

        logger.bind(
            pipeline_id=pipeline_id,
            version=new_version,
            x_trace_id=x_trace_id,
        ).info("pipeline.version_created")

        return {
            "pipeline_id": pipeline_id,
            "version_number": new_version,
            "vector_table_name": vector_table_name,
            "pipeline_version_id": str(new_version_row.id),
        }

    async def get_active_config(
        self,
        *,
        pipeline_id: str,
        organization_id: str,
    ) -> dict | None:
        """Resolve the pipeline's current config_snapshot -- the config of the
        pipeline_versions row matching pipelines.current_version. Used to
        seed GraphState.variant_config before a graph dispatch so Builder/
        Ingestion pick up whatever the pipeline's active version was created
        with (e.g. an applied Improver recommendation). Returns None (never
        a fabricated default) if the pipeline has no version row yet or the
        row has no config_snapshot -- callers fall back to graph node
        defaults in that case, same as before this method existed.
        """
        org_uuid = uuid.UUID(organization_id)
        pip_uuid = uuid.UUID(pipeline_id)

        pipeline = await self._repo.get_by_id(pipeline_id=pip_uuid, organization_id=org_uuid)
        if pipeline is None:
            raise PipelineNotFoundError(
                f"Pipeline {pipeline_id} not found in org {organization_id}."
            )

        version = await self._version_repo.get_by_pipeline_and_version(
            pipeline_id=pip_uuid,
            organization_id=org_uuid,
            version_number=pipeline.current_version,
        )
        return version.config_snapshot if version else None

    async def rollback_to_version(
        self,
        *,
        pipeline_id: str,
        organization_id: str,
        version_number: int,
    ) -> dict:
        """Point the pipeline back at an earlier version's config -- does NOT
        touch pipeline_chunks (Version 4, migration 0016): every version's
        chunks are real, isolated rows in the shared table, untouched by
        later versions' rebuilds, so this is a trivial config-pointer flip,
        not a rebuild or delete. The next evaluation/query dispatch will
        both read this version's config_snapshot (get_active_config()) AND
        retrieve against this version's own chunks (pipeline_version filter
        derived from the now-current_version), so rollback is fully real.

        Raises:
            PipelineNotFoundError: If pipeline_id has no such version.
        """
        org_uuid = uuid.UUID(organization_id)
        pip_uuid = uuid.UUID(pipeline_id)

        version = await self._version_repo.get_by_pipeline_and_version(
            pipeline_id=pip_uuid, organization_id=org_uuid, version_number=version_number
        )
        if version is None:
            raise PipelineNotFoundError(
                f"Pipeline {pipeline_id} has no version {version_number} to roll back to."
            )

        await self._repo.update_current_version(
            pipeline_id=pip_uuid,
            organization_id=org_uuid,
            current_version=version_number,
            chunk_strategy=version.chunk_strategy,
            embedding_model=version.embedding_model,
        )
        await self.db.commit()

        return {"pipeline_id": pipeline_id, "current_version": version_number}

    async def list_versions_with_scores(
        self,
        *,
        pipeline_id: str,
        organization_id: str,
    ) -> list[dict]:
        """Real version history for the Pipeline Evolution / optimization
        timeline UI. unified_score/latency_p95_ms/cost_usd/recall per version
        resolve from the evaluation_runs row linked via the experiment_runs
        row whose result_pipeline_version_id matches this version (both set
        once an apply-improvement re-evaluation completes -- see
        OptimizerService, migration 0015). Every field falls back to None
        (never fabricated) for a version with no completed evaluation yet.
        """
        org_uuid = uuid.UUID(organization_id)
        pip_uuid = uuid.UUID(pipeline_id)

        pipeline = await self._repo.get_by_id(pipeline_id=pip_uuid, organization_id=org_uuid)
        if pipeline is None:
            raise PipelineNotFoundError(
                f"Pipeline {pipeline_id} not found in org {organization_id}."
            )

        versions = await self._version_repo.list_by_pipeline(
            pipeline_id=pip_uuid, organization_id=org_uuid
        )
        experiments = await self._experiment_repo.list_by_pipeline(
            pipeline_id=pip_uuid, organization_id=org_uuid
        )
        experiment_by_version_id = {
            exp.result_pipeline_version_id: exp
            for exp in experiments
            if exp.result_pipeline_version_id is not None
        }

        # Fan out to the (small, per-pipeline-version) set of real
        # evaluation_runs rows linked from each applied experiment -- gives
        # latency/cost/recall, which live only on evaluation_runs.
        eval_run_ids = {
            exp.result_evaluation_run_id
            for exp in experiment_by_version_id.values()
            if exp.result_evaluation_run_id is not None
        }
        eval_run_by_id = {}
        for eval_run_id in eval_run_ids:
            run = await self._eval_repo.get_by_id(
                evaluation_run_id=eval_run_id, organization_id=org_uuid
            )
            if run is not None:
                eval_run_by_id[eval_run_id] = run

        result = []
        for v in versions:
            exp = experiment_by_version_id.get(v.id)
            eval_run = (
                eval_run_by_id.get(exp.result_evaluation_run_id)
                if exp and exp.result_evaluation_run_id is not None
                else None
            )
            is_current = v.version_number == pipeline.current_version

            unified_score = (
                float(pipeline.unified_score)
                if is_current and pipeline.unified_score is not None
                else (float(exp.unified_score) if exp and exp.unified_score is not None else None)
            )

            result.append({
                "version_number": v.version_number,
                "chunk_strategy": v.chunk_strategy,
                "embedding_model": v.embedding_model,
                "config_snapshot": v.config_snapshot,
                "unified_score": unified_score,
                "recall": float(eval_run.recall) if eval_run and eval_run.recall is not None else None,
                "latency_p95_ms": eval_run.latency_p95_ms if eval_run else None,
                "cost_usd": float(eval_run.cost_usd) if eval_run and eval_run.cost_usd is not None else None,
                "score_delta": float(exp.score_delta) if exp and exp.score_delta is not None else None,
                "vector_table_name": v.vector_table_name,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            })
        return result


def _pipeline_to_dict(pipeline: Pipeline) -> dict:
    """Serialize a Pipeline ORM instance to a plain dict for API responses."""
    return {
        "id": str(pipeline.id),
        "organization_id": str(pipeline.organization_id),
        "name": pipeline.name,
        "status": pipeline.status,
        "chunk_strategy": pipeline.chunk_strategy,
        "embedding_model": pipeline.embedding_model,
        "unified_score": float(pipeline.unified_score) if pipeline.unified_score else None,
        "current_version": pipeline.current_version,
        "created_at": pipeline.created_at.isoformat() if pipeline.created_at else None,
        "updated_at": pipeline.updated_at.isoformat() if pipeline.updated_at else None,
    }

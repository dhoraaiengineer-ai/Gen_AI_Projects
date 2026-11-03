"""OptimizerService — applies a real Improver recommendation, rebuilds, and
re-evaluates. Distinct from ImproverAgent (app/graph/nodes/improver.py),
which only *generates* candidate configs with no side effects: this service
is the only thing that *applies*, *rebuilds*, *compares real scores*, and
*decides continue/stop* (Phase 5). Sits at the orchestration layer (routes ->
services -> repositories, Rule 10) and drives repeated whole-graph dispatches
through the existing single graph entry point (`ingestion`) -- no GraphState
or graph-topology change (see plan doc: "Optimizer is a service layer, not a
new LangGraph node").

Never fabricates a score: if the applied variant performs worse than the
parent run, that real (negative) score_delta is persisted and returned
as-is -- never clamped, hidden, or silently retried into a better number.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.state import GraphState, format_pipeline_version, initial_state
from app.repositories.evaluation_repository import EvaluationRepository
from app.repositories.experiment_run_repository import ExperimentRunRepository
from app.repositories.pipeline_repository import PipelineRepository
from app.schemas.optimize import ApplyImprovementResponse, ConfigDiffEntry
from app.services.evaluation_dispatch import run_and_persist_evaluation
from app.services.ground_truth_service import (
    default_golden_path_question,
    is_golden_path_document,
)
from app.services.pipeline_service import PipelineService
from app.services.vector_service import VectorService

logger = structlog.get_logger(__name__)


class VariantNotFoundError(Exception):
    """Raised when the requested run_id/variant_id doesn't match a real,
    persisted Improver candidate. Never silently falls back to a fabricated
    config."""


class MissingQueryError(Exception):
    """Raised when no query was supplied and the pipeline isn't the golden-path
    demo document -- mirrors POST /evaluate's own 422 (app/routes/evaluate.py),
    never silently dispatches an empty query."""


def _diff_config(current: dict | None, new: dict) -> list[ConfigDiffEntry]:
    """Real field-by-field diff between the pipeline's current config and the
    candidate being applied. Only fields present on either side are compared
    -- no invented "expected effect" text (that would require a claim this
    service can't verify)."""
    current = current or {}
    fields = sorted(set(current) | set(new))
    entries = []
    for field in fields:
        old_val = current.get(field)
        new_val = new.get(field)
        if old_val != new_val:
            entries.append(ConfigDiffEntry(field=field, from_value=old_val, to_value=new_val))
    return entries


class OptimizerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._eval_repo = EvaluationRepository(db)
        self._experiment_repo = ExperimentRunRepository(db)
        self._pipeline_svc = PipelineService(db)

    async def prepare_apply_improvement(
        self,
        *,
        pipeline_id: str,
        organization_id: str,
        source_run_id: str,
        variant_id: str,
        user_id: str,
        x_trace_id: str,
        query: str | None = None,
    ) -> tuple[GraphState, str, ApplyImprovementResponse]:
        """Validate the request, persist the new pipeline version + a pending
        experiment_runs row + a pending evaluation_runs row, and build the
        GraphState for dispatch.

        Returns (graph_state, new_run_id, response) -- the caller (route)
        dispatches `graph_state` via BackgroundTasks; nothing here touches
        FastAPI's BackgroundTasks directly, keeping this service framework-
        agnostic (Rule 10).

        Raises:
            PipelineNotFoundError: pipeline doesn't exist / wrong org.
            VariantNotFoundError: source_run_id has no matching Improver
                candidate for variant_id -- never fabricated.
        """
        org_uuid = uuid.UUID(organization_id)
        pip_uuid = uuid.UUID(pipeline_id)

        source_run = await self._eval_repo.get_by_run_id(
            run_id=uuid.UUID(source_run_id), organization_id=org_uuid
        )
        if source_run is None:
            raise VariantNotFoundError(f"Evaluation run {source_run_id} not found.")

        metadata = source_run.agent_execution_metadata or {}
        candidates = metadata.get("improver_candidates")
        if not isinstance(candidates, list):
            raise VariantNotFoundError(
                f"Evaluation run {source_run_id} has no Improver candidates."
            )
        candidate = next((c for c in candidates if c.get("variant_id") == variant_id), None)
        if candidate is None:
            raise VariantNotFoundError(
                f"Variant {variant_id} not found among run {source_run_id}'s candidates."
            )

        candidate_config = candidate.get("config")
        if not isinstance(candidate_config, dict):
            raise VariantNotFoundError(
                f"Variant {variant_id} has no structured config to apply."
            )

        old_score = float(source_run.unified_score) if source_run.unified_score is not None else None

        resolved_query = await self._resolve_query(pipeline_id, organization_id, query)

        current_config = await self._pipeline_svc.get_active_config(
            pipeline_id=pipeline_id, organization_id=organization_id
        )
        config_diff = _diff_config(current_config, candidate_config)

        # Real rebuild for every apply -- per the architecture decision, the
        # compiled graph has exactly one entry point (`ingestion`), and
        # ingestion_node already re-downloads/re-lists source documents from
        # Storage on every run regardless of whether chunk_strategy actually
        # changed, so always re-running the full chain is both the simple
        # AND the correct choice (no stale-index risk from skipping it).
        version_meta = await self._pipeline_svc.create_version(
            pipeline_id=pipeline_id,
            organization_id=organization_id,
            config=candidate_config,
            x_trace_id=x_trace_id,
        )
        new_version = version_meta["version_number"]
        # 20-Jul-2026 (Version 4): dispatch under the NEW version string, not
        # the pipeline's previous one -- pipeline_chunks (migration 0016)
        # partitions rows by this exact value, so this is what makes the
        # rebuild write real, isolated rows instead of overwriting the old
        # version's chunks in place. Without this, every apply-improvement
        # rebuild would silently dispatch initial_state()'s "v1" default
        # forever, regardless of how many versions had actually been created.
        new_pipeline_version = format_pipeline_version(new_version)

        experiment_run = await self._experiment_repo.create(
            pipeline_id=pip_uuid,
            organization_id=org_uuid,
            parent_evaluation_run_id=source_run.id,
            variant_config=candidate_config,
            status="running",
            result_pipeline_version_id=uuid.UUID(version_meta["pipeline_version_id"]),
        )

        new_run_id = uuid.uuid4()
        await self._eval_repo.create(
            pipeline_id=pip_uuid,
            organization_id=org_uuid,
            run_id=new_run_id,
            dataset_version=source_run.dataset_version,
            status="pending",
        )

        await self.db.commit()

        graph_state = initial_state(
            run_id=str(new_run_id),
            pipeline_id=pipeline_id,
            organization_id=organization_id,
            x_trace_id=x_trace_id,
            user_id=user_id,
            session_id=str(uuid.uuid4()),
            raw_query=resolved_query,
            pipeline_version=new_pipeline_version,
            variant_config=candidate_config,
        )

        logger.bind(
            pipeline_id=pipeline_id,
            experiment_run_id=str(experiment_run.id),
            new_run_id=str(new_run_id),
            variant_id=variant_id,
            x_trace_id=x_trace_id,
        ).info("optimizer.apply_improvement_dispatched")

        response = ApplyImprovementResponse(
            experiment_run_id=str(experiment_run.id),
            job_id=str(new_run_id),
            pipeline_id=pipeline_id,
            new_version=new_version,
            old_score=old_score,
            config_diff=config_diff,
            status="pending",
        )
        return graph_state, str(experiment_run.id), response

    async def _resolve_query(
        self, pipeline_id: str, organization_id: str, query: str | None
    ) -> str:
        """Mirrors POST /evaluate's own resolution exactly (app/routes/evaluate.py):
        explicit caller-supplied query first, else the golden-path demo document's
        real curated question, else a real error -- never a silently empty query,
        which would hard-block at Evaluator on faithfulness=0.0."""
        resolved = (query or "").strip()
        if resolved:
            return resolved
        # 20-Jul-2026 (Version 4): must check the pipeline's REAL current
        # version's chunks, not a hardcoded "v1.0" -- pipeline_chunks
        # (migration 0016) partitions by the exact version string.
        current_version = await self._current_pipeline_version(pipeline_id, organization_id)
        is_golden_path = await is_golden_path_document(
            vector_service=VectorService(db=self.db),
            pipeline_id=pipeline_id,
            pipeline_version=current_version,
            organization_id=organization_id,
        )
        if is_golden_path:
            return default_golden_path_question().query
        raise MissingQueryError(
            "A non-empty 'query' is required to re-evaluate this pipeline "
            "(dataset-driven evaluation is only available for the golden-path "
            "demo document)."
        )

    async def _current_pipeline_version(self, pipeline_id: str, organization_id: str) -> str:
        """Real current_version -> canonical GraphState.pipeline_version string."""
        pipeline_row = await self._pipeline_svc.get_by_id(
            pipeline_id=pipeline_id, organization_id=organization_id
        )
        return format_pipeline_version(pipeline_row["current_version"])

    async def dispatch_and_await_evaluation(
        self,
        *,
        pipeline_id: str,
        organization_id: str,
        user_id: str,
        x_trace_id: str,
        app_state: object,
        query: str | None = None,
    ) -> uuid.UUID:
        """Dispatch one real evaluation against the pipeline's CURRENT active
        config and wait for it to complete (unlike POST /evaluate's fire-and-
        poll, this awaits inline -- used only from run_optimization_loop,
        which is itself already a background task iterating sequentially).
        Returns the new run's UUID (the evaluation_runs.run_id column) so the
        caller can read back the real score/faithfulness/candidates.
        """
        resolved_query = await self._resolve_query(pipeline_id, organization_id, query)
        active_config = await self._pipeline_svc.get_active_config(
            pipeline_id=pipeline_id, organization_id=organization_id
        )
        current_version = await self._current_pipeline_version(pipeline_id, organization_id)

        run_id = uuid.uuid4()
        await self._eval_repo.create(
            pipeline_id=uuid.UUID(pipeline_id),
            organization_id=uuid.UUID(organization_id),
            run_id=run_id,
            dataset_version="latest",
            status="pending",
        )
        await self.db.commit()

        state = initial_state(
            run_id=str(run_id),
            pipeline_id=pipeline_id,
            organization_id=organization_id,
            x_trace_id=x_trace_id,
            user_id=user_id,
            session_id=str(uuid.uuid4()),
            raw_query=resolved_query,
            pipeline_version=current_version,
            variant_config=active_config,
        )
        await run_and_persist_evaluation(state, app_state)
        return run_id

    async def run_optimization_loop(
        self,
        *,
        pipeline_id: str,
        organization_id: str,
        user_id: str,
        x_trace_id: str,
        app_state: object,
        target_score: float,
        max_iterations: int,
        query: str | None = None,
    ) -> None:
        """Bounded autonomous loop: evaluate -> (apply best real candidate if
        one exists) -> re-evaluate -> repeat, until target_score is reached,
        max_iterations is exhausted, a real stop condition fires, or 3
        consecutive iterations show no real improvement. Every iteration's
        outcome is a real evaluation run + experiment_runs row -- nothing here
        invents a score or silently retries past a safety block.

        Stop conditions (each is a REAL, honestly-logged reason, matching the
        exact semantics already used elsewhere in this platform -- never
        invented new ones):
          - target_reached: unified_score >= target_score.
          - blocked_faithfulness: faithfulness < 0.5 (evaluator-standards.md
            Rule 2 / CLAUDE.md Sec 9's hard block -- non-bypassable here too).
          - hitl_required: score is in the 0.70-0.84 human-approval band. The
            graph itself pauses at the `hitl` node for this band and does NOT
            run Diagnoser/Improver, so there is no real candidate to apply
            without a human first approving -- Optimizer must not bypass
            that (workflow-contracts.md Rule 9: "Human Approval Must Be
            Explicit").
          - no_candidates: score < 0.70 but this run produced no Improver
            candidates (should not normally happen -- the graph auto-runs
            Improver in this band -- but never assumed).
          - no_improvement: 3 consecutive iterations with score delta < 0.01
            (mirrors the platform's existing max_retries=3 ceiling pattern,
            app/core/workflow.py `_route_after_observer`).
          - max_iterations_reached: loop exhausted without reaching target.
        """
        consecutive_no_improvement = 0
        last_score: float | None = None
        source_run_id: uuid.UUID | None = None
        pending_candidate: dict | None = None

        # `create_version()` (called inside `prepare_apply_improvement`, and by
        # the bare POST /versions route) sets pipeline.status = "running" with
        # nothing downstream ever resetting it -- confirmed via a live-server
        # probe: an empty-body POST to this endpoint left a real demo pipeline
        # permanently stuck on "running" after an unhandled MissingQueryError
        # crashed this method outright. The try/finally below guarantees the
        # status returns to "ready" exactly once, however the loop ends
        # (a real stop condition, max_iterations, or any exception) -- this is
        # the single reset point for the whole bounded loop; per-iteration
        # calls to run_apply_improvement_background pass
        # reset_pipeline_status=False so they don't flip it back mid-loop.
        try:
            for iteration in range(1, max_iterations + 1):
                if pending_candidate is not None and source_run_id is not None:
                    # Apply the previous iteration's chosen candidate, then read
                    # back the resulting re-evaluation -- reuses the exact same
                    # apply+rebuild+re-evaluate path POST /apply-improvement uses.
                    try:
                        graph_state, experiment_run_id, response = await self.prepare_apply_improvement(
                            pipeline_id=pipeline_id,
                            organization_id=organization_id,
                            source_run_id=str(source_run_id),
                            variant_id=pending_candidate["variant_id"],
                            user_id=user_id,
                            x_trace_id=x_trace_id,
                            query=query,
                        )
                    except (VariantNotFoundError, MissingQueryError) as exc:
                        logger.error(
                            "optimizer.loop_apply_failed",
                            extra={"pipeline_id": pipeline_id, "iteration": iteration, "error": str(exc)},
                        )
                        break
                    await run_apply_improvement_background(
                        graph_state,
                        app_state,
                        experiment_run_id=experiment_run_id,
                        organization_id=organization_id,
                        old_score=response.old_score,
                        reset_pipeline_status=False,
                    )
                    run_id = uuid.UUID(response.job_id)
                else:
                    try:
                        run_id = await self.dispatch_and_await_evaluation(
                            pipeline_id=pipeline_id,
                            organization_id=organization_id,
                            user_id=user_id,
                            x_trace_id=x_trace_id,
                            app_state=app_state,
                            query=query,
                        )
                    except MissingQueryError as exc:
                        logger.error(
                            "optimizer.loop_evaluate_failed",
                            extra={"pipeline_id": pipeline_id, "iteration": iteration, "error": str(exc)},
                        )
                        break

                run = await self._eval_repo.get_by_run_id(
                    run_id=run_id, organization_id=uuid.UUID(organization_id)
                )
                if run is None:
                    logger.error(
                        "optimizer.loop_run_missing",
                        extra={"pipeline_id": pipeline_id, "iteration": iteration, "run_id": str(run_id)},
                    )
                    break

                score = float(run.unified_score) if run.unified_score is not None else None
                faithfulness = float(run.faithfulness) if run.faithfulness is not None else None

                stop_reason: str | None = None
                if faithfulness is not None and faithfulness < 0.5:
                    stop_reason = "blocked_faithfulness"
                elif score is not None and score >= target_score:
                    stop_reason = "target_reached"
                elif score is not None and 0.70 <= score < 0.85:
                    stop_reason = "hitl_required"

                if stop_reason:
                    logger.bind(
                        pipeline_id=pipeline_id, iteration=iteration, score=score, reason=stop_reason,
                    ).info("optimizer.loop_stopped")
                    return

                if last_score is not None and score is not None and (score - last_score) < 0.01:
                    consecutive_no_improvement += 1
                else:
                    consecutive_no_improvement = 0
                if consecutive_no_improvement >= 3:
                    logger.bind(
                        pipeline_id=pipeline_id, iteration=iteration, score=score, reason="no_improvement",
                    ).info("optimizer.loop_stopped")
                    return
                last_score = score

                metadata = run.agent_execution_metadata or {}
                candidates = metadata.get("improver_candidates")
                winner = next((c for c in candidates if c.get("is_winner")), None) if isinstance(candidates, list) else None
                if winner is None or not isinstance(winner.get("config"), dict):
                    logger.bind(
                        pipeline_id=pipeline_id, iteration=iteration, score=score, reason="no_candidates",
                    ).info("optimizer.loop_stopped")
                    return

                source_run_id = run.run_id
                pending_candidate = winner

            logger.bind(
                pipeline_id=pipeline_id, max_iterations=max_iterations, reason="max_iterations_reached",
            ).info("optimizer.loop_stopped")
        finally:
            try:
                async with AsyncSessionLocal() as session:
                    await PipelineRepository(session).update_status(
                        pipeline_id=uuid.UUID(pipeline_id),
                        organization_id=uuid.UUID(organization_id),
                        status="ready",
                    )
                    await session.commit()
            except Exception as exc:  # noqa: BLE001 -- status reset must never mask the real loop outcome
                logger.error(
                    "optimizer.pipeline_status_reset_failed",
                    extra={"pipeline_id": pipeline_id, "error": str(exc)},
                )

    async def rollback_to_version(
        self,
        *,
        pipeline_id: str,
        organization_id: str,
        version_number: int,
        x_trace_id: str,
    ) -> dict:
        """Thin delegation to PipelineService.rollback_to_version -- kept as a
        method here too since Optimizer is the natural caller (undoing a bad
        autonomous iteration) and callers of this service shouldn't need to
        know PipelineService exists separately."""
        result = await self._pipeline_svc.rollback_to_version(
            pipeline_id=pipeline_id,
            organization_id=organization_id,
            version_number=version_number,
        )
        logger.bind(
            pipeline_id=pipeline_id, version_number=version_number, x_trace_id=x_trace_id,
        ).info("optimizer.rolled_back")
        return result


async def run_apply_improvement_background(
    graph_state: GraphState,
    app_state: object,
    *,
    experiment_run_id: str,
    organization_id: str,
    old_score: float | None,
    reset_pipeline_status: bool = True,
) -> None:
    """Background task: dispatch the graph via the shared evaluation runner,
    then update the experiment_runs bookkeeping row with the REAL outcome
    (never fabricated -- a regression is persisted as a negative score_delta,
    not hidden or retried into a better number).

    `create_version()` (called before this task is dispatched) sets
    `pipeline.status = "running"` for the duration of the rebuild. This
    function is the natural place to flip it back once real work is done --
    but `run_optimization_loop` also calls this per-iteration internally, and
    the pipeline must stay "running" across the WHOLE bounded loop, not flip
    to "ready" after iteration 1. `reset_pipeline_status=False` lets the loop
    own its own single reset (see `run_optimization_loop`'s `finally` block);
    the standalone `POST /apply-improvement` route (the only other caller)
    keeps the default `True` since nothing else runs after it."""
    try:
        await run_and_persist_evaluation(graph_state, app_state)

        async with AsyncSessionLocal() as session:
            eval_repo = EvaluationRepository(session)
            experiment_repo = ExperimentRunRepository(session)

            new_run = await eval_repo.get_by_run_id(
                run_id=uuid.UUID(graph_state["run_id"]),
                organization_id=uuid.UUID(organization_id),
            )
            if new_run is None:
                logger.error(
                    "optimizer.apply_improvement_result_run_missing",
                    extra={"experiment_run_id": experiment_run_id, "run_id": graph_state["run_id"]},
                )
                return

            new_score = float(new_run.unified_score) if new_run.unified_score is not None else None
            score_delta = (
                round(new_score - old_score, 4) if new_score is not None and old_score is not None else None
            )
            final_status = "completed" if new_run.status == "completed" else new_run.status

            await experiment_repo.update_result(
                experiment_run_id=uuid.UUID(experiment_run_id),
                organization_id=uuid.UUID(organization_id),
                status=final_status,
                unified_score=new_score,
                score_delta=score_delta,
                result_evaluation_run_id=new_run.id,
            )
            await session.commit()

            logger.bind(
                experiment_run_id=experiment_run_id,
                old_score=old_score,
                new_score=new_score,
                score_delta=score_delta,
            ).info("optimizer.apply_improvement_completed")
    except Exception as exc:  # noqa: BLE001 -- must never crash a background task silently (Rule 85)
        logger.error(
            "optimizer.apply_improvement_result_persist_failed",
            extra={"experiment_run_id": experiment_run_id, "error": str(exc)},
        )
    finally:
        if reset_pipeline_status:
            try:
                async with AsyncSessionLocal() as session:
                    await PipelineRepository(session).update_status(
                        pipeline_id=uuid.UUID(graph_state["pipeline_id"]),
                        organization_id=uuid.UUID(organization_id),
                        status="ready",
                    )
                    await session.commit()
            except Exception as exc:  # noqa: BLE001 -- status reset must never crash the task
                logger.error(
                    "optimizer.pipeline_status_reset_failed",
                    extra={"pipeline_id": graph_state["pipeline_id"], "error": str(exc)},
                )

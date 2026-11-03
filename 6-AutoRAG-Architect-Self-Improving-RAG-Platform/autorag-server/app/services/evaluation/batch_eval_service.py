"""Service -- batch evaluation orchestration.

Dispatches every 'approved' golden question in a published dataset version
against a pipeline, one real LangGraph run each, reusing
evaluation_dispatch.run_and_persist_evaluation (the exact function
POST /evaluate and OptimizerService.apply_and_evaluate already use) --
never reimplements retrieval+generation+scoring. Rule 86 cost/latency
guardrails are inherited for free through that reuse.

Rate-limit pacing (V4 MVP, 26-Jul-2026): a fixed SAMPLE_COOLDOWN sleep
between each question's dispatch, sized for a free-tier judge provider
(e.g. Groq llama-3.1-8b-instant, 6,000 TPM) -- without it, N questions in a
batch fire N judge-LLM bursts back-to-back and 429 well before the batch
finishes. This is deliberately NOT a retry-on-429 mechanism: LLMService.call()
already has real multi-provider failover (Gemini -> KiMi -> Gemini) as its
resilience story, and duplicating a bespoke retry loop here would work
against that, not with it -- pacing prevents the 429 in the first place
rather than reacting to one. Version 5: provider-aware adaptive pacing (see
VERSION_5_ROADMAP.md) instead of this fixed constant.

Per-question ground truth flows through GraphState.variant_config (see
app/graph/nodes/evaluator.py's 24-Jul-2026 change) -- no new GraphState
field, since variant_config already exists as the seeding mechanism
ingestion.py/builder.py read chunk_strategy/retrieval params from.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import (
    BatchRunNotFoundError,
    DatasetVersionNotPublishedError,
    EmptyDatasetVersionError,
    EvaluationFailedError,
)
from app.core.state import initial_state
from app.models.batch_evaluation import BatchEvaluation, BatchRun
from app.models.evaluation_config import EvaluationConfig
from app.models.evaluation_dataset import GoldenQuestion
from app.repositories.batch_evaluation_repository import BatchEvaluationRepository
from app.repositories.evaluation_config_repository import EvaluationConfigRepository
from app.repositories.evaluation_dataset_repository import EvaluationDatasetRepository
from app.repositories.evaluation_repository import EvaluationRepository
from app.services.evaluation_dispatch import run_and_persist_evaluation

logger = structlog.get_logger(__name__)

# Error classification (V4, 26-Jul-2026) -- a real, user-visible reason for a
# failed question, not just "failed". Pattern-matched against the exception's
# own str() rather than isinstance checks against provider-specific exception
# classes, since LLMProviderError's message already embeds the underlying
# httpx status/error text (see LLMService.call()'s "All LLM providers
# exhausted..." message) and this needs to classify across whichever provider
# actually failed, not one specific SDK's exception hierarchy.
def _classify_error(exc: Exception) -> tuple[str, str]:
    """Returns (error_type, user_message). Falls through to a generic
    classification rather than raising -- this runs inside an already-caught
    exception handler and must never itself fail."""
    text = str(exc).lower()
    if "429" in text or "rate limit" in text or "rate_limit" in text:
        return "RATE_LIMIT", "Rate limit exceeded on the judge provider."
    if "timeout" in text or isinstance(exc, TimeoutError):
        return "TIMEOUT", "Judge provider timed out."
    if "connection" in text or isinstance(exc, ConnectionError):
        return "CONNECTION_ERROR", "Network connection to the judge provider was lost."
    if "auth" in text or "401" in text or "403" in text or "api key" in text:
        return "AUTHENTICATION_ERROR", "Judge provider rejected the API credentials."
    if isinstance(exc, EvaluationFailedError):
        return "EVALUATION_FAILED", str(exc) or "Evaluation failed."
    return "UNKNOWN", str(exc) or "Unexpected evaluation error."


def _build_variant_config(
    config: EvaluationConfig | None, question: GoldenQuestion
) -> dict:
    """Merge an EvaluationConfig's real, graph-honored fields (top_k,
    chunk_size -- see app/graph/nodes/builder.py|ingestion.py's vc.get(...)
    call sites) with this question's ground truth. reranker/embedding_model/
    judge_provider/judge_model/retriever_strategy/temperature are stored on
    EvaluationConfig for reproducibility/display but are NOT currently read
    by any graph node -- do not claim they change execution."""
    variant_config: dict = {}
    if config is not None:
        if config.top_k is not None:
            variant_config["top_k"] = config.top_k
        if config.chunk_size is not None:
            variant_config["chunk_size"] = config.chunk_size
    if question.reference_answer:
        variant_config["ground_truth"] = question.reference_answer
    if question.relevant_chunk_ids:
        variant_config["relevant_chunk_ids"] = question.relevant_chunk_ids
    return variant_config


class BatchEvalService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._batch_repo = BatchEvaluationRepository(db)
        self._dataset_repo = EvaluationDatasetRepository(db)
        self._config_repo = EvaluationConfigRepository(db)

    async def start_batch_run(
        self,
        *,
        dataset_version_id: str,
        pipeline_id: str,
        config_id: str | None,
        organization_id: str,
        user_id: str,
        x_trace_id: str,
        app_state: object,
    ) -> BatchRun:
        """Creates the batch_run header + all pending batch_evaluations rows,
        commits (so the caller gets an id back immediately), then dispatches
        every question sequentially as a background task."""
        org_uuid = uuid.UUID(organization_id)
        version_uuid = uuid.UUID(dataset_version_id)

        version = await self._dataset_repo.get_version_by_id(
            version_id=version_uuid, organization_id=org_uuid
        )
        if version is None or version.lifecycle_status != "published":
            raise DatasetVersionNotPublishedError(
                dataset_version_id, version.lifecycle_status if version else "not_found"
            )

        questions = await self._dataset_repo.list_published_questions(
            dataset_version_id=version_uuid, organization_id=org_uuid
        )
        if not questions:
            raise EmptyDatasetVersionError(dataset_version_id)

        config_uuid = uuid.UUID(config_id) if config_id else None
        batch_run = await self._batch_repo.create_batch_run(
            organization_id=org_uuid,
            dataset_version_id=version_uuid,
            pipeline_id=uuid.UUID(pipeline_id),
            config_id=config_uuid,
            created_by=uuid.UUID(user_id),
        )
        await self._batch_repo.create_pending_rows(
            batch_run_id=batch_run.id,
            organization_id=org_uuid,
            dataset_version_id=version_uuid,
            pipeline_id=uuid.UUID(pipeline_id),
            config_id=config_uuid,
            golden_question_ids=[q.id for q in questions],
        )
        await self.db.commit()

        logger.info(
            "batch_run.created",
            extra={
                "batch_run_id": str(batch_run.id),
                "question_count": len(questions),
                "x_trace_id": x_trace_id,
            },
        )
        return batch_run

    async def dispatch_batch_run(
        self,
        *,
        batch_run_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: str,
        x_trace_id: str,
        app_state: object,
    ) -> None:
        """Background task -- dispatches every 'pending' row for this batch
        run sequentially. Never raises: any per-question failure marks that
        row 'failed' and moves on, so one bad question never aborts the rest
        of the batch (Rule 85: don't let one failure cascade)."""
        async with AsyncSessionLocal() as session:
            batch_repo = BatchEvaluationRepository(session)
            dataset_repo = EvaluationDatasetRepository(session)
            config_repo = EvaluationConfigRepository(session)
            eval_repo = EvaluationRepository(session)

            batch_run = await batch_repo.get_batch_run(
                batch_run_id=batch_run_id, organization_id=organization_id
            )
            if batch_run is None:
                logger.error("batch_run_not_found_for_dispatch", extra={"batch_run_id": str(batch_run_id)})
                return

            await batch_repo.set_batch_run_status(
                batch_run_id=batch_run_id,
                organization_id=organization_id,
                status="running",
                started_at=datetime.now(UTC),
            )
            await session.commit()

            config = None
            if batch_run.config_id is not None:
                config = await config_repo.get_by_id(
                    config_id=batch_run.config_id, organization_id=organization_id
                )

            pending_rows = await batch_repo.list_pending_or_failed(
                batch_run_id=batch_run_id, organization_id=organization_id
            )
            sample_cooldown = get_settings().batch_eval_sample_cooldown_seconds

            for i, row in enumerate(pending_rows):
                await self._dispatch_one_question(
                    row=row,
                    config=config,
                    organization_id=organization_id,
                    user_id=user_id,
                    x_trace_id=x_trace_id,
                    app_state=app_state,
                    batch_repo=batch_repo,
                    dataset_repo=dataset_repo,
                    eval_repo=eval_repo,
                    session=session,
                )
                # Rate-limit pacing (V4 MVP) -- skip after the last question,
                # nothing left to protect against a burst.
                if i < len(pending_rows) - 1 and sample_cooldown > 0:
                    await asyncio.sleep(sample_cooldown)

            remaining = await batch_repo.list_pending_or_failed(
                batch_run_id=batch_run_id, organization_id=organization_id
            )
            final_status = "completed" if not any(r.status == "pending" for r in remaining) else "failed"
            await batch_repo.set_batch_run_status(
                batch_run_id=batch_run_id,
                organization_id=organization_id,
                status=final_status,
                completed_at=datetime.now(UTC),
            )
            await session.commit()

            logger.info(
                "batch_run.dispatched_complete",
                extra={"batch_run_id": str(batch_run_id), "status": final_status},
            )

    async def _dispatch_one_question(
        self,
        *,
        row: BatchEvaluation,
        config: EvaluationConfig | None,
        organization_id: uuid.UUID,
        user_id: str,
        x_trace_id: str,
        app_state: object,
        batch_repo: BatchEvaluationRepository,
        dataset_repo: EvaluationDatasetRepository,
        eval_repo: EvaluationRepository,
        session: AsyncSession,
    ) -> None:
        try:
            question = await dataset_repo.get_question_by_id(
                question_id=row.golden_question_id, organization_id=organization_id
            )
            if question is None:
                await batch_repo.mark_failed(
                    batch_evaluation_id=row.id,
                    organization_id=organization_id,
                    error_message="Golden question was deleted or is no longer accessible.",
                    error_type="QUESTION_NOT_FOUND",
                )
                await session.commit()
                return

            await batch_repo.mark_running(
                batch_evaluation_id=row.id, organization_id=organization_id
            )
            await session.commit()

            run_id = uuid.uuid4()
            await eval_repo.create(
                pipeline_id=row.pipeline_id,
                organization_id=organization_id,
                run_id=run_id,
                dataset_version=str(row.dataset_version_id),
                status="pending",
            )
            await session.commit()

            state = initial_state(
                run_id=str(run_id),
                pipeline_id=str(row.pipeline_id),
                organization_id=str(organization_id),
                x_trace_id=x_trace_id,
                user_id=user_id,
                session_id=str(uuid.uuid4()),
                raw_query=question.question,
                variant_config=_build_variant_config(config, question),
            )
            await run_and_persist_evaluation(state, app_state)

            eval_run = await eval_repo.get_by_run_id(
                run_id=run_id, organization_id=organization_id
            )
            if eval_run is not None:
                await batch_repo.mark_completed(
                    batch_evaluation_id=row.id,
                    organization_id=organization_id,
                    evaluation_run_id=eval_run.id,
                )
            else:
                await batch_repo.mark_failed(
                    batch_evaluation_id=row.id,
                    organization_id=organization_id,
                    error_message="Evaluation did not produce a result — the pipeline run "
                    "failed before completion.",
                    error_type="EVALUATION_INCOMPLETE",
                )
            await session.commit()
        except Exception as exc:
            error_type, error_message = _classify_error(exc)
            logger.error(
                "batch_evaluation.question_dispatch_failed",
                extra={
                    "batch_evaluation_id": str(row.id),
                    "error": str(exc),
                    "error_type": error_type,
                    "x_trace_id": x_trace_id,
                },
            )
            await batch_repo.mark_failed(
                batch_evaluation_id=row.id,
                organization_id=organization_id,
                error_message=error_message,
                error_type=error_type,
            )
            await session.commit()

    async def prepare_resume(self, *, batch_run_id: str, organization_id: str) -> BatchRun:
        """Validates the batch run can be resumed and returns it -- the
        route then dispatches the SAME dispatch_batch_run background task
        used by start_batch_run, which already only re-queries
        'pending'/'failed' rows (list_pending_or_failed), so resume and
        initial dispatch share one code path rather than two."""
        org_uuid = uuid.UUID(organization_id)
        run_uuid = uuid.UUID(batch_run_id)
        batch_run = await self._batch_repo.get_batch_run(
            batch_run_id=run_uuid, organization_id=org_uuid
        )
        if batch_run is None:
            raise BatchRunNotFoundError(f"Batch run {batch_run_id} not found")
        if batch_run.status == "running":
            raise ValueError(f"Batch run {batch_run_id} is already running")
        return batch_run

    async def cancel_batch_run(self, *, batch_run_id: str, organization_id: str) -> None:
        org_uuid = uuid.UUID(organization_id)
        run_uuid = uuid.UUID(batch_run_id)
        batch_run = await self._batch_repo.get_batch_run(
            batch_run_id=run_uuid, organization_id=org_uuid
        )
        if batch_run is None:
            raise BatchRunNotFoundError(f"Batch run {batch_run_id} not found")

        # Only 'pending' rows are touched -- an already-'running' row is left
        # to finish (deployment-policies.md Rule 8/10: no killing an
        # in-flight graph invocation).
        await self._batch_repo.cancel_pending_rows(
            batch_run_id=run_uuid, organization_id=org_uuid
        )
        await self._batch_repo.set_batch_run_status(
            batch_run_id=run_uuid,
            organization_id=org_uuid,
            status="cancelled",
            cancelled_at=datetime.now(UTC),
        )
        await self.db.commit()

    async def get_batch_run_summary(self, *, batch_run_id: str, organization_id: str) -> dict:
        org_uuid = uuid.UUID(organization_id)
        run_uuid = uuid.UUID(batch_run_id)
        batch_run = await self._batch_repo.get_batch_run(
            batch_run_id=run_uuid, organization_id=org_uuid
        )
        if batch_run is None:
            raise BatchRunNotFoundError(f"Batch run {batch_run_id} not found")
        summary = await self._batch_repo.get_batch_run_summary(
            batch_run_id=run_uuid, organization_id=org_uuid
        )
        worst = await self._batch_repo.get_worst_scoring(
            batch_run_id=run_uuid, organization_id=org_uuid
        )
        return {
            "batch_run": batch_run,
            "summary": summary,
            "worst_scoring": worst,
        }

    async def get_result_detail(self, *, batch_evaluation_id: str, organization_id: str) -> dict:
        """Result Detail inspector's data source. Only returns what is
        genuinely persisted in evaluation_runs.agent_execution_metadata /
        ragas_metrics -- no fabricated 'Prompt' or 'Retrieved Chunks'
        section for data that isn't captured (that raw context is not
        persisted anywhere today -- PII-masking scope, not this service's
        to invent)."""
        org_uuid = uuid.UUID(organization_id)
        result = await self._batch_repo.get_with_evaluation_run(
            batch_evaluation_id=uuid.UUID(batch_evaluation_id), organization_id=org_uuid
        )
        if result is None:
            raise BatchRunNotFoundError(f"Batch evaluation {batch_evaluation_id} not found")
        batch_evaluation, evaluation_run = result
        return {
            "batch_evaluation": batch_evaluation,
            "evaluation_run": evaluation_run,
        }

    async def export_batch_run(self, *, batch_run_id: str, organization_id: str) -> list[dict]:
        """Serialized rows for CSV/JSON/XLSX export -- the route layer picks
        the output format; this returns plain dicts either way."""
        org_uuid = uuid.UUID(organization_id)
        rows = await self._batch_repo.list_by_batch_run(
            batch_run_id=uuid.UUID(batch_run_id), organization_id=org_uuid, limit=10_000
        )
        out = []
        for row in rows:
            eval_run = None
            if row.evaluation_run_id is not None:
                eval_run = await EvaluationRepository(self.db).get_by_id(
                    evaluation_run_id=row.evaluation_run_id, organization_id=org_uuid
                )
            out.append(
                {
                    "batch_evaluation_id": str(row.id),
                    "golden_question_id": str(row.golden_question_id),
                    "status": row.status,
                    "review_status": row.review_status,
                    "unified_score": float(eval_run.unified_score)
                    if eval_run and eval_run.unified_score is not None
                    else None,
                    "faithfulness": float(eval_run.faithfulness)
                    if eval_run and eval_run.faithfulness is not None
                    else None,
                }
            )
        return out

"""Shared LangGraph dispatch-and-persist logic for evaluation runs.

20-Jul-2026: extracted from app/routes/evaluate.py (was a route-private
`_run_eval_workflow` background task) so app/services/optimizer_service.py
can reuse the exact same dispatch + persistence logic for Apply Improvement
re-evaluations, without a service depending on a route module (Rule 00
layering: routes -> services -> repositories, never the reverse) or
duplicating ~150 lines of careful evaluation_runs persistence.

Both POST /evaluate and OptimizerService.apply_and_evaluate call
`run_and_persist_evaluation(state, app_state)` as a FastAPI BackgroundTasks
target -- identical dispatch, identical persistence semantics.
"""

from __future__ import annotations

import uuid

import structlog

from app.core.database import AsyncSessionLocal
from app.core.state import GraphState
from app.repositories.evaluation_repository import EvaluationRepository

logger = structlog.get_logger(__name__)

# Matches app/routes/retrieve.py's RetrievedChunkOut.preview truncation --
# same PII-safety discipline (never the full raw chunk text), reused here
# so /retrieve and evaluation_runs.agent_execution_metadata stay consistent.
_CHUNK_PREVIEW_LEN = 240


def build_retrieved_context_preview(final_state: GraphState) -> list[dict] | None:
    """Safe, truncated preview of what was actually retrieved for this run.

    V4 fast-follow (26-Jul-2026): final_state["retrieved_chunks"] was always
    computed by builder.py but discarded before persistence -- every
    evaluation_runs row's "Retrieved Context" was permanently unavailable.
    Mirrors RetrievedChunkOut's exact field mapping (retrieve.py) so the two
    surfaces render identically; skips the document_id DB lookup that route
    does (an extra query not worth adding to this background persist path --
    source_uri is shown as-is instead)."""
    chunks = final_state.get("retrieved_chunks")
    if not chunks:
        return None
    preview = []
    for rank, c in enumerate(chunks, start=1):
        text = c.get("chunk_text") or ""
        preview.append(
            {
                "chunk_id": c.get("chunk_id"),
                "rank": rank,
                "retrieval_score": c.get("retrieval_score"),
                "rerank_score": c.get("score"),
                "source_uri": c.get("source_uri"),
                "page_number": c.get("page_number"),
                "chunk_strategy": c.get("chunk_strategy"),
                "preview": text[:_CHUNK_PREVIEW_LEN],
            }
        )
    return preview


def build_failure_taxonomy(final_state: GraphState, *, blocked: bool) -> dict | None:
    """Build the value persisted to evaluation_runs.failure_taxonomy.

    Two mutually-exclusive shapes (guardrail_blocked short-circuits before
    Diagnoser ever runs -- app/core/workflow.py's _route_after_evaluator):
      - Guardrail hard block (blocked=True): {"error_type": ...} -- pre-existing.
      - Diagnoser actually ran (blocked=False, retry loop reached it at least
        once): the real classification -- GET /diagnose/{run_id} (app/routes/
        diagnose.py) reads exactly this shape. Previously never persisted here,
        so that route always returned null diagnosis data for every real run
        (Part E, 12-Jul-2026 fix).
      - Neither (a well-scoring run that never entered the retry loop): None.
    """
    if blocked:
        return {"error_type": final_state.get("guardrail_block_reason") or "guardrail_blocked"}
    if final_state.get("failure_type") is not None:
        return {
            "failure_type": final_state.get("failure_type"),
            "confidence": final_state.get("confidence"),
            "remediation_hint": final_state.get("remediation_hint"),
            "root_cause_analysis": final_state.get("root_cause_analysis"),
        }
    return None


async def run_and_persist_evaluation(state: GraphState, app_state: object) -> None:
    """Background task: invoke LangGraph workflow from ingestion through evaluator,
    then persist the result to evaluation_runs. Never raises -- all failures are
    caught and persisted as a "failed" run so GET /jobs/{id} always reaches a
    terminal state (Rule 85: don't swallow exceptions silently)."""
    try:
        workflow = getattr(app_state, "workflow", None)
        if workflow is None:
            logger.error("workflow_not_available", extra={"x_trace_id": state.get("x_trace_id", "")})
            return
        config = {
            "configurable": {
                # run_id, not pipeline_id -- pipeline_id is reused across every
                # evaluation of the same pipeline, so it collided on the shared
                # app.state.workflow MemorySaver's checkpoint thread when a
                # second evaluation started before the first's checkpoint
                # history was cleared, hanging in "pending" indefinitely
                # (live-confirmed 17-Jul-2026). approve.py (HITL) never calls
                # workflow.ainvoke()/resumes a checkpoint by thread_id -- it's
                # a pure DB status write -- so nothing relies on reusing
                # pipeline_id as the thread across separate evaluation calls;
                # run_id is unique per call and carries no such risk.
                "thread_id": state["run_id"],
                "x_trace_id": state["x_trace_id"],
            }
        }
        final_state = await workflow.ainvoke(state, config=config)

        # Persist the graph's result — no other node writes evaluation_runs on
        # success, so without this the run stays "pending" forever even when
        # the workflow completed cleanly (see verification/releases audit follow-up).
        blocked = bool(final_state.get("guardrail_blocked"))
        adversarial_pass_rate = final_state.get("adversarial_pass_rate")

        # P0.5 fix (12-Jul-2026): a HITL-band score (0.70 <= unified_score < 0.85)
        # routes to the `hitl` node, which calls LangGraph's interrupt() and
        # pauses the graph -- ainvoke() returns normally at that point (it does
        # not raise), so final_state reflects a run that is NOT actually
        # finished, just paused awaiting POST /approve/{run_id}. Without this
        # check every HITL-pending run was persisted as status="completed",
        # which is false: no node after `evaluator` (deployer included) has
        # run yet. `approval_status` is only set once /approve resumes the
        # graph (workflow.py's resume nodes), so its absence here means the
        # interrupt is still pending.
        awaiting_approval = bool(final_state.get("approval_required")) and not final_state.get(
            "approval_status"
        )
        if awaiting_approval:
            run_status = "pending_approval"
        elif blocked:
            run_status = "blocked"
        else:
            run_status = "completed"

        # Node-level status/timing, Observer signals, Improver's full
        # candidate set, and adversarial per-question failures were all
        # computed by the graph but previously discarded here — see
        # verification/releases/v4.0/audit/METRICS_WIRING_MATRIX.md. Only include a key when
        # the corresponding node actually ran and produced it (e.g. a run
        # blocked before Improver has no improver_candidates).
        agent_execution_metadata: dict = {
            "node_trace": final_state.get("execution_trace") or [],
        }
        # V4 fast-follow (26-Jul-2026): both real GraphState values, previously
        # computed then discarded before persistence -- see
        # build_retrieved_context_preview()'s docstring above.
        retrieved_context_preview = build_retrieved_context_preview(final_state)
        if retrieved_context_preview is not None:
            agent_execution_metadata["retrieved_context_preview"] = retrieved_context_preview
        if final_state.get("generated_answer"):
            agent_execution_metadata["generated_answer"] = final_state["generated_answer"]
        # P0.6-3 (13-Jul-2026): recall/quality inputs and the full score
        # provenance trail (formula version, weights, penalty factors) --
        # threaded through ragas_metrics by evaluator.py (Step 6) since
        # neither is a top-level GraphState field. Reads back out here so
        # evaluation_runs.recall/quality (real Numeric columns that existed
        # since migration 0002 but were never written) and the provenance
        # blob both get persisted, closing the "unified_score can't be
        # explained without transient GraphState" gap.
        ragas_metrics_out = final_state.get("ragas_metrics") or {}
        score_provenance = ragas_metrics_out.get("score_provenance")
        if score_provenance is not None:
            agent_execution_metadata["score_provenance"] = score_provenance
        if final_state.get("error_rate") is not None:
            agent_execution_metadata["observer_signals"] = {
                "error_rate": final_state.get("error_rate"),
                "quality_trend": final_state.get("quality_trend"),
                "alert_triggered": final_state.get("alert_triggered"),
                "observation_flags": final_state.get("observation_flags"),
            }
        if final_state.get("improver_candidates") is not None:
            agent_execution_metadata["improver_candidates"] = final_state.get(
                "improver_candidates"
            )
            agent_execution_metadata["improvement_attempt"] = final_state.get(
                "improvement_attempt"
            )
        if final_state.get("adversarial_failures") is not None:
            agent_execution_metadata["adversarial_failures"] = final_state.get(
                "adversarial_failures"
            )

        try:
            async with AsyncSessionLocal() as session:
                await EvaluationRepository(session).update_score(
                    run_id=uuid.UUID(state["run_id"]),
                    organization_id=uuid.UUID(state["organization_id"]),
                    unified_score=final_state.get("unified_score"),
                    # P0.6-3: recall/quality are real Numeric columns
                    # (migration 0002) that stayed NULL because nothing ever
                    # passed them here — the frontend's ScoreResult.recall/
                    # quality are typed non-null, so score.py returning null
                    # crashed EvidenceViewer/RootCausePanel's .toFixed(2)
                    # calls on any real Diagnoser page view.
                    recall=ragas_metrics_out.get("recall"),
                    quality=ragas_metrics_out.get("quality"),
                    faithfulness=final_state.get("faithfulness"),
                    latency_p95_ms=final_state.get("latency_p95_ms"),
                    cost_usd=(score_provenance or {}).get("cost_usd_input"),
                    ragas_metrics=final_state.get("ragas_metrics"),
                    adversarial_passed=(
                        adversarial_pass_rate == 1.0 if adversarial_pass_rate is not None else None
                    ),
                    status=run_status,
                    failure_taxonomy=build_failure_taxonomy(final_state, blocked=blocked),
                    agent_execution_metadata=agent_execution_metadata,
                )
                await session.commit()
        except Exception as persist_exc:
            logger.error(
                "eval_workflow_success_persist_failed",
                extra={"error": str(persist_exc), "x_trace_id": state.get("x_trace_id", "")},
            )
    except Exception as exc:
        logger.error(
            "eval_workflow_failed",
            extra={"error": str(exc), "x_trace_id": state.get("x_trace_id", "")},
        )
        # The request-scoped session is already closed by the time this
        # background task runs — open a fresh one to persist the failure
        # so GET /jobs/{id} stops reporting "pending" forever (Rule 85:
        # don't swallow exceptions silently).
        try:
            async with AsyncSessionLocal() as session:
                await EvaluationRepository(session).update_score(
                    run_id=uuid.UUID(state["run_id"]),
                    organization_id=uuid.UUID(state["organization_id"]),
                    unified_score=None,
                    status="failed",
                    failure_taxonomy={"error_type": "workflow_exception"},
                )
                await session.commit()
        except Exception as persist_exc:
            logger.error(
                "eval_workflow_failure_persist_failed",
                extra={"error": str(persist_exc), "x_trace_id": state.get("x_trace_id", "")},
            )

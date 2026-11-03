"""Integration tests for the Apply Improvement feature (20-Jul-2026) --
real Supabase PostgreSQL, no mocking of the DB layer (Rule 80).

Covers the DB-backed service methods that don't require a full LangGraph
dispatch (no LLM/embedding calls): PipelineService.create_version's two
regression fixes (version persistence, config sync), get_active_config
resolution, rollback_to_version, list_versions_with_scores, and
OptimizerService.prepare_apply_improvement's validation + real config diff.

The full background dispatch path (run_apply_improvement_background,
run_optimization_loop) reuses run_and_persist_evaluation, which is the
pre-existing, already-covered `_run_eval_workflow` logic moved verbatim to
app/services/evaluation_dispatch.py (see that module's docstring) -- its
correctness isn't newly at risk from this feature, so it isn't re-tested
here; a full end-to-end run would require the same LLM/embedding stubbing
`tests/conftest.py`'s MockEmbedder pattern provides elsewhere.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PipelineNotFoundError
from app.services.optimizer_service import (
    MissingQueryError,
    OptimizerService,
    VariantNotFoundError,
)
from app.services.pipeline_service import PipelineService


async def _seed_organization(db_session: AsyncSession) -> uuid.UUID:
    org_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO organizations (id, name, slug) "
            "VALUES (:id, :name, :slug)"
        ),
        {"id": str(org_id), "name": f"Test Org {org_id}", "slug": f"test-org-{org_id}"},
    )
    return org_id


async def _seed_evaluation_run_with_candidates(
    db_session: AsyncSession,
    *,
    pipeline_id: uuid.UUID,
    organization_id: uuid.UUID,
    unified_score: float,
    winner_config: dict,
    winner_variant_id: str = "variant-a",
) -> uuid.UUID:
    """Directly insert an evaluation_runs row carrying real-shaped
    improver_candidates JSON (matching app/routes/improve.py's read shape) --
    no LangGraph dispatch needed to test candidate resolution/diffing."""
    run_id = uuid.uuid4()
    metadata = {
        "improver_candidates": [
            {
                "variant_id": winner_variant_id,
                "config": winner_config,
                "unified_score": 0.9,
                "score_delta": 0.1,
                "is_winner": True,
            }
        ]
    }
    await db_session.execute(
        text(
            "INSERT INTO evaluation_runs "
            "(id, pipeline_id, organization_id, run_id, unified_score, status, "
            "agent_execution_metadata, dataset_version) "
            "VALUES (:pk, :pipeline_id, :org_id, :run_id, :score, 'completed', "
            "CAST(:metadata AS JSONB), 'latest')"
        ),
        {
            "pk": str(uuid.uuid4()),
            "pipeline_id": str(pipeline_id),
            "org_id": str(organization_id),
            "run_id": str(run_id),
            "score": unified_score,
            "metadata": json.dumps(metadata),
        },
    )
    return run_id


@pytest.mark.asyncio
class TestPipelineServiceVersioning:
    """Regression tests for the two real create_version() bugs fixed
    20-Jul-2026: current_version was never persisted, and config was only
    ever written to the audit log, never onto the pipeline row."""

    async def test_create_seeds_a_real_v1_row(self, db_session: AsyncSession) -> None:
        org_id = await _seed_organization(db_session)
        svc = PipelineService(db_session)

        pipeline = await svc.create(
            name=f"pipe-{uuid.uuid4()}",
            config_yaml=None,
            organization_id=str(org_id),
            x_trace_id="test-trace",
            chunk_strategy="semantic",
        )

        versions = await svc.list_versions_with_scores(
            pipeline_id=pipeline["id"], organization_id=str(org_id)
        )
        assert len(versions) == 1
        assert versions[0]["version_number"] == 1
        assert versions[0]["chunk_strategy"] == "semantic"

    async def test_create_version_persists_version_bump_and_config(
        self, db_session: AsyncSession
    ) -> None:
        org_id = await _seed_organization(db_session)
        svc = PipelineService(db_session)
        pipeline = await svc.create(
            name=f"pipe-{uuid.uuid4()}",
            config_yaml=None,
            organization_id=str(org_id),
            x_trace_id="test-trace",
            chunk_strategy="semantic",
        )

        result = await svc.create_version(
            pipeline_id=pipeline["id"],
            organization_id=str(org_id),
            config={"chunk_strategy": "hierarchical", "k_value": 10},
            x_trace_id="test-trace",
        )
        assert result["version_number"] == 2

        # The real bug: calling create_version a second time previously
        # recomputed the SAME version number, because current_version was
        # never written back to the DB. Assert it's genuinely 3, not 2 again.
        result2 = await svc.create_version(
            pipeline_id=pipeline["id"],
            organization_id=str(org_id),
            config={"chunk_strategy": "late"},
            x_trace_id="test-trace",
        )
        assert result2["version_number"] == 3

        active_config = await svc.get_active_config(
            pipeline_id=pipeline["id"], organization_id=str(org_id)
        )
        assert active_config == {"chunk_strategy": "late"}

        updated = await svc.get_by_id(pipeline_id=pipeline["id"], organization_id=str(org_id))
        assert updated["chunk_strategy"] == "late"
        assert updated["current_version"] == 3

    async def test_rollback_restores_earlier_version_config(
        self, db_session: AsyncSession
    ) -> None:
        org_id = await _seed_organization(db_session)
        svc = PipelineService(db_session)
        pipeline = await svc.create(
            name=f"pipe-{uuid.uuid4()}",
            config_yaml=None,
            organization_id=str(org_id),
            x_trace_id="test-trace",
            chunk_strategy="semantic",
        )
        await svc.create_version(
            pipeline_id=pipeline["id"],
            organization_id=str(org_id),
            config={"chunk_strategy": "hierarchical"},
            x_trace_id="test-trace",
        )

        result = await svc.rollback_to_version(
            pipeline_id=pipeline["id"], organization_id=str(org_id), version_number=1
        )
        assert result["current_version"] == 1

        updated = await svc.get_by_id(pipeline_id=pipeline["id"], organization_id=str(org_id))
        assert updated["chunk_strategy"] == "semantic"

    async def test_rollback_to_nonexistent_version_raises(
        self, db_session: AsyncSession
    ) -> None:
        org_id = await _seed_organization(db_session)
        svc = PipelineService(db_session)
        pipeline = await svc.create(
            name=f"pipe-{uuid.uuid4()}",
            config_yaml=None,
            organization_id=str(org_id),
            x_trace_id="test-trace",
        )
        with pytest.raises(PipelineNotFoundError):
            await svc.rollback_to_version(
                pipeline_id=pipeline["id"], organization_id=str(org_id), version_number=99
            )


@pytest.mark.asyncio
class TestOptimizerServicePrepareApplyImprovement:
    """OptimizerService.prepare_apply_improvement -- validation, real config
    diff, and version/experiment_run bookkeeping. Does not dispatch the
    graph (see module docstring)."""

    async def test_variant_not_found_for_unknown_run(self, db_session: AsyncSession) -> None:
        org_id = await _seed_organization(db_session)
        svc = OptimizerService(db_session)
        with pytest.raises(VariantNotFoundError):
            await svc.prepare_apply_improvement(
                pipeline_id=str(uuid.uuid4()),
                organization_id=str(org_id),
                source_run_id=str(uuid.uuid4()),
                variant_id="does-not-exist",
                user_id="tester",
                x_trace_id="test-trace",
            )

    async def test_variant_not_found_for_unknown_variant_id(
        self, db_session: AsyncSession
    ) -> None:
        org_id = await _seed_organization(db_session)
        pipeline_svc = PipelineService(db_session)
        pipeline = await pipeline_svc.create(
            name=f"pipe-{uuid.uuid4()}",
            config_yaml=None,
            organization_id=str(org_id),
            x_trace_id="test-trace",
        )
        run_id = await _seed_evaluation_run_with_candidates(
            db_session,
            pipeline_id=uuid.UUID(pipeline["id"]),
            organization_id=org_id,
            unified_score=0.72,
            winner_config={"chunk_strategy": "hierarchical"},
            winner_variant_id="variant-a",
        )
        await db_session.commit()

        svc = OptimizerService(db_session)
        with pytest.raises(VariantNotFoundError):
            await svc.prepare_apply_improvement(
                pipeline_id=pipeline["id"],
                organization_id=str(org_id),
                source_run_id=str(run_id),
                variant_id="variant-does-not-exist",
                user_id="tester",
                x_trace_id="test-trace",
            )

    async def test_prepare_produces_real_diff_and_persists_version(
        self, db_session: AsyncSession
    ) -> None:
        org_id = await _seed_organization(db_session)
        pipeline_svc = PipelineService(db_session)
        pipeline = await pipeline_svc.create(
            name=f"pipe-{uuid.uuid4()}",
            config_yaml=None,
            organization_id=str(org_id),
            x_trace_id="test-trace",
            chunk_strategy="semantic",
        )
        run_id = await _seed_evaluation_run_with_candidates(
            db_session,
            pipeline_id=uuid.UUID(pipeline["id"]),
            organization_id=org_id,
            unified_score=0.72,
            winner_config={"chunk_strategy": "hierarchical", "k_value": 10},
            winner_variant_id="variant-a",
        )
        await db_session.commit()

        svc = OptimizerService(db_session)
        _graph_state, experiment_run_id, response = await svc.prepare_apply_improvement(
            pipeline_id=pipeline["id"],
            organization_id=str(org_id),
            source_run_id=str(run_id),
            variant_id="variant-a",
            user_id="tester",
            x_trace_id="test-trace",
            query="What is the refund policy?",
        )

        assert response.old_score == 0.72
        assert response.new_version == 2
        assert experiment_run_id  # a real experiment_runs row was created
        diff_fields = {entry.field for entry in response.config_diff}
        assert "chunk_strategy" in diff_fields
        assert "k_value" in diff_fields

        versions = await pipeline_svc.list_versions_with_scores(
            pipeline_id=pipeline["id"], organization_id=str(org_id)
        )
        assert len(versions) == 2
        assert versions[1]["chunk_strategy"] == "hierarchical"

    async def test_missing_query_raises_for_non_golden_path_pipeline(
        self, db_session: AsyncSession
    ) -> None:
        org_id = await _seed_organization(db_session)
        pipeline_svc = PipelineService(db_session)
        pipeline = await pipeline_svc.create(
            name=f"pipe-{uuid.uuid4()}",
            config_yaml=None,
            organization_id=str(org_id),
            x_trace_id="test-trace",
        )
        run_id = await _seed_evaluation_run_with_candidates(
            db_session,
            pipeline_id=uuid.UUID(pipeline["id"]),
            organization_id=org_id,
            unified_score=0.72,
            winner_config={"chunk_strategy": "hierarchical"},
        )
        await db_session.commit()

        svc = OptimizerService(db_session)
        with pytest.raises(MissingQueryError):
            await svc.prepare_apply_improvement(
                pipeline_id=pipeline["id"],
                organization_id=str(org_id),
                source_run_id=str(run_id),
                variant_id="variant-a",
                user_id="tester",
                x_trace_id="test-trace",
                query=None,
            )


@pytest.mark.asyncio
class TestPipelineStatusNeverStaysStuckOnRunning:
    """Regression test for the real bug found 20-Jul-2026 via live endpoint
    testing: an empty-body POST /pipelines/{id}/optimize against a pipeline
    with no documents crashed with an unhandled MissingQueryError, and
    nothing ever reset pipeline.status back from "running" -- it stayed
    stuck permanently in production data, with no client-facing endpoint
    able to unstick it (PATCH /pipelines/{id} only allows draft->pending).

    Reproduces the exact sequence: a prior version bump leaves the pipeline
    "running" (create_version()'s documented in-flight-rebuild signal), then
    run_optimization_loop's first iteration fails immediately (no documents,
    no explicit query, not the golden-path demo) before ever reaching
    app_state/the graph -- app_state=None is safe here for that reason."""

    async def test_loop_resets_status_even_when_first_iteration_fails(
        self, db_session: AsyncSession
    ) -> None:
        org_id = await _seed_organization(db_session)
        pipeline_svc = PipelineService(db_session)
        pipeline = await pipeline_svc.create(
            name=f"pipe-{uuid.uuid4()}",
            config_yaml=None,
            organization_id=str(org_id),
            x_trace_id="test-trace",
        )
        # Simulate an in-flight rebuild leaving the pipeline "running" --
        # matches the real repro sequence (a version bump immediately
        # preceding the optimize call that then crashed).
        await pipeline_svc.create_version(
            pipeline_id=pipeline["id"],
            organization_id=str(org_id),
            config={},
            x_trace_id="test-trace",
        )
        await db_session.commit()
        mid_flight = await pipeline_svc.get_by_id(
            pipeline_id=pipeline["id"], organization_id=str(org_id)
        )
        assert mid_flight["status"] == "running"

        svc = OptimizerService(db_session)
        # Must not raise -- the loop's own MissingQueryError handling must
        # catch this and break cleanly, not propagate as an unhandled crash.
        await svc.run_optimization_loop(
            pipeline_id=pipeline["id"],
            organization_id=str(org_id),
            user_id="tester",
            x_trace_id="test-trace",
            app_state=None,
            target_score=0.85,
            max_iterations=3,
            query=None,
        )

        updated = await pipeline_svc.get_by_id(
            pipeline_id=pipeline["id"], organization_id=str(org_id)
        )
        assert updated["status"] == "ready", (
            "pipeline.status must never stay stuck on 'running' after "
            "run_optimization_loop exits, regardless of how it exits"
        )

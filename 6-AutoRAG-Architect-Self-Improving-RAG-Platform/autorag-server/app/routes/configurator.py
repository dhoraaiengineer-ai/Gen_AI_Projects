"""POST /api/v1/configurator — 6-step wizard -> validated pipeline config + pipeline row."""

from __future__ import annotations

from typing import Literal

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import AuthenticatedUser
from app.core.database import get_db
from app.core.dependencies import get_organization_id, get_trace_id
from app.services.pipeline_service import PipelineService

logger = structlog.get_logger(__name__)

router = APIRouter()


class ConfiguratorStep1(BaseModel):
    """Step 1: Pipeline name and document type."""
    name: str
    doc_type: Literal["pdf", "docx", "txt", "html", "mixed"]


class ConfiguratorStep2(BaseModel):
    """Step 2: Chunking strategy selection."""
    chunk_strategy: Literal["semantic", "hierarchical", "late"]
    chunk_size: int = Field(default=512, ge=128, le=4096)
    chunk_overlap: int = Field(default=64, ge=0, le=512)


class ConfiguratorStep3(BaseModel):
    """Step 3: Retrieval configuration."""
    retrieval_mode: Literal["dense", "hybrid", "hybrid+hyde"]
    top_k: int = Field(default=10, ge=1, le=50)
    reranker: Literal["cohere", "bge"] = "cohere"


class ConfiguratorStep4(BaseModel):
    """Step 4: LLM configuration."""
    llm_provider: Literal["gemini-flash-3.5", "kimi-k2.6", "gemini-3.5"] = "gemini-flash-3.5"
    max_tokens: int = Field(default=2048, ge=256, le=8192)
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)


class ConfiguratorStep5(BaseModel):
    """Step 5: Evaluation configuration."""
    eval_dataset_version: str = "v1.0"
    min_unified_score: float = Field(default=0.85, ge=0.70, le=1.0)


class ConfiguratorStep6(BaseModel):
    """Step 6: Deploy target."""
    deploy_target: Literal["ecs-fargate", "local"] = "ecs-fargate"
    auto_deploy: bool = False


class ConfiguratorRequest(BaseModel):
    """Full 6-step wizard payload submitted as one request."""
    step1: ConfiguratorStep1
    step2: ConfiguratorStep2
    step3: ConfiguratorStep3
    step4: ConfiguratorStep4
    step5: ConfiguratorStep5
    step6: ConfiguratorStep6


@router.post("")
async def create_pipeline_config(
    body: ConfiguratorRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """
    Accepts the completed 6-step wizard form and:
    1. Builds a YAML config from the wizard answers
    2. Creates a pipeline DB row
    3. Returns the pipeline_id for /ingest to start loading documents

    The YAML config is stored on the pipeline row and used by the LangGraph
    ingestion node to apply the right chunk strategy and retrieval settings.
    """
    import yaml  # bundled with PyYAML via langchain deps

    config = {
        "pipeline": {
            "name": body.step1.name,
            "doc_type": body.step1.doc_type,
        },
        "chunking": {
            "strategy": body.step2.chunk_strategy,
            "chunk_size": body.step2.chunk_size,
            "chunk_overlap": body.step2.chunk_overlap,
        },
        "retrieval": {
            "mode": body.step3.retrieval_mode,
            "top_k": body.step3.top_k,
            "reranker": body.step3.reranker,
        },
        "llm": {
            "provider": body.step4.llm_provider,
            "max_tokens": body.step4.max_tokens,
            "temperature": body.step4.temperature,
        },
        "evaluation": {
            "dataset_version": body.step5.eval_dataset_version,
            "min_unified_score": body.step5.min_unified_score,
        },
        "deployment": {
            "target": body.step6.deploy_target,
            "auto_deploy": body.step6.auto_deploy,
        },
    }
    config_yaml = yaml.dump(config, default_flow_style=False)

    # 25-Jul-2026 fix: previously only chunk_strategy reached the pipeline's
    # v1 config_snapshot (via PipelineService.create()'s own default) -- every
    # other wizard setting below was baked into config_yaml only, which
    # nothing at ingestion/retrieval/generation time ever reads back. This is
    # exactly what GraphState.variant_config / get_active_config() already
    # know how to consume (see ingestion.py/builder.py's vc.get(...) reads).
    # min_unified_score (step5) is deliberately excluded -- CLAUDE.md Forbidden
    # Pattern #2 forbids a configurable bypass of the >= 0.85 deployment gate.
    # "hybrid+hyde" maps to the existing hyde_enabled flag builder.py already
    # reads (bool(vc.get("hyde_enabled", False))) -- retrieval_mode itself
    # only distinguishes dense vs hybrid at the SearchService.hybrid_search()
    # level; HyDE is a separate, already-real mechanism layered on top.
    variant_config = {
        "chunk_size": body.step2.chunk_size,
        "chunk_overlap": body.step2.chunk_overlap,
        "retrieval_mode": "dense" if body.step3.retrieval_mode == "dense" else "hybrid",
        "hyde_enabled": body.step3.retrieval_mode == "hybrid+hyde",
        "top_k": body.step3.top_k,
        "reranker_enabled": True,
        "reranker": body.step3.reranker,
        "llm_provider": body.step4.llm_provider,
        "temperature": body.step4.temperature,
        "max_tokens": body.step4.max_tokens,
    }

    svc = PipelineService(db)
    pipeline = await svc.create(
        name=body.step1.name,
        config_yaml=config_yaml,
        organization_id=organization_id,
        x_trace_id=trace_id,
        chunk_strategy=body.step2.chunk_strategy,
        variant_config=variant_config,
    )

    logger.info(
        "configurator.pipeline_created",
        extra={"pipeline_id": pipeline["id"], "x_trace_id": trace_id},
    )

    return {
        "status": "ok",
        "data": {
            "pipeline_id": pipeline["id"],
            "config": config,
            "config_yaml": config_yaml,
            "message": "Pipeline configured. Upload documents via POST /api/v1/ingest.",
        },
        "error": None,
        "request_id": trace_id,
    }

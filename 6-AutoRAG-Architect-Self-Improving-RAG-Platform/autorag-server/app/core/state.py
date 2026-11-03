"""LangGraph GraphState — authoritative state contract for the 9-node AutoRAG loop.

AUTHORITATIVE LOCATION: app/core/state.py
app/graph/state.py is a backward-compatibility re-export shim — do not import from there in new code.

This is the SINGLE SOURCE OF TRUTH for all state flowing between agent nodes.
See .claude/rules/graph-state-governance.md for field ownership rules.

LOCKED: No field may be added or removed without Architecture Review.
Any change requires approval from project lead (Mahesh Kumar).

ARCHITECTURE REVIEW APPROVED (12-Jul-2026, Mahesh Kumar): added 3 fields --
adversarial_failures, improver_candidates, observation_flags. Root cause:
LangGraph's StateGraph(GraphState) only tracks declared TypedDict fields as
merge channels; nodes were returning these as undeclared keys (with
`# type: ignore[typeddict-item]`), which were silently dropped during
inter-node state merging and never reached evaluate.py's persistence layer.
See verification/releases/v4.0/audit/METRICS_WIRING_MATRIX.md. Central persistence path is
preserved -- these are real GraphState fields, not a new per-node DB write
path: Agent Nodes -> GraphState -> evaluate.py orchestration persistence ->
EvaluationRun.agent_execution_metadata -> Repository -> API -> Frontend.

Rules:
- All agent nodes MUST read from and write to this state object only.
- No agent node may store state in instance variables, globals, or external cache.
- PII must be masked before any field is written here (Rule 70, graph-state-governance Rule 6).
- x_trace_id must be propagated unchanged through every node (graph-state-governance Rule 7).
- cost_usd/tokens go in execution_trace only — never add agent_metrics to GraphState (Rule 86).

Spec: .claude/specs/agents/ (one file per agent)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from typing_extensions import TypedDict


class GraphState(TypedDict, total=False):
    """
    Shared state object for the AutoRAG 9-agent LangGraph loop.

    All fields are optional (total=False):
    - nodes only write the fields they produce
    - additive schema evolution remains backward compatible

    Field ownership (see graph-state-governance.md Rule 2):
    | Node            | Writes                                                          |
    |-----------------|------------------------------------------------------------------|
    | API boundary    | run_id, pipeline_id, organization_id, x_trace_id,               |
    |                 | user_id, session_id, created_at, updated_at, deployment_id      |
    | Query Rewriter  | rewritten_query, query_embedding                                |
    | Builder         | retrieved_chunks, retrieved_document_count, retrieval_latency_ms|
    |                 | hyde_document, retrieval_strategy                               |
    | Compressor      | compressed_context, token_count, chunks, chunk_strategy         |
    | Generator       | generated_answer, llm_provider_used, generation_latency_ms     |
    | Evaluator       | unified_score, faithfulness, groundedness_score, relevance_score|
    |                 | ragas_metrics, adversarial_pass_rate, adversarial_pass,         |
    |                 | adversarial_failures, latency_p95_ms, cost_per_query_usd        |
    | Observer        | error_rate, quality_trend, alert_triggered, observation_flags   |
    | Diagnoser       | failure_type, failure_analysis, confidence,                     |
    |                 | remediation_hint, root_cause_analysis, retry_count             |
    | Improver        | variant_config, variant_id, improvement_attempt, score_delta,   |
    |                 | improver_candidates                                              |
    | Deployer        | deployment_decision, deploy_status, ecs_task_arn,               |
    |                 | ecr_image_uri, blue/green task ARNs, rollback_reason            |
    """

    # ─────────────────────────────────────────────────────────────
    # Schema Metadata
    # ─────────────────────────────────────────────────────────────

    graph_state_version: str             # always "v1.0" — never change at runtime

    # ─────────────────────────────────────────────────────────────
    # Orchestration Boundary  [API boundary — read-only for all nodes]
    # ─────────────────────────────────────────────────────────────

    run_id: str                          # UUID v7 — unique per pipeline run
    pipeline_id: str                     # UUID v7 — which pipeline config
    pipeline_version: str                # e.g. "v1.3"
    organization_id: str                 # UUID v7 — multi-tenant scoping (required)
    x_trace_id: str                      # UUID v7 — distributed trace (NEVER mutate)

    user_id: str | None                  # UUID v7 — cost attribution + HITL routing
    session_id: str | None               # UUID v7 — groups runs in one session
    created_at: str                      # ISO 8601 UTC — run initiation timestamp
    updated_at: str                      # ISO 8601 UTC — last state mutation
    deployment_id: str | None            # UUID v7 — ECS deployment for rollback attribution

    # ─────────────────────────────────────────────────────────────
    # Execution Trace  [appended by EVERY node — Rule 86]
    # ─────────────────────────────────────────────────────────────

    execution_trace: list[dict[str, Any]]
    """
    Each entry shape (cost fields populated by LLMService only — Rule 86):
    {
        "node": str,
        "timestamp": str (ISO 8601),
        "x_trace_id": str,
        "graph_state_version": str,
        "latency_ms": int,
        "status": str,           # "success" | "failed" | "retried"
        "retry_count": int,
        "cost_usd": float,       # LLMService only
        "provider": str,         # LLMService only
        "prompt_tokens": int,    # LLMService only
        "completion_tokens": int # LLMService only
    }
    """

    # ─────────────────────────────────────────────────────────────
    # Query Rewriter  [Agent 2 — Team 3]
    # ─────────────────────────────────────────────────────────────

    raw_query: str                       # original user query (PII-masked before insertion)
    rewritten_query: str | None          # improved query from Query Rewriter

    query_embedding: list[float] | None  # 768-dim embedding (Gemini Embedding 2)

    # ─────────────────────────────────────────────────────────────
    # Builder / Retrieval  [Agent 3 — Team 6 — 4-stage retrieval]
    # ─────────────────────────────────────────────────────────────

    retrieved_chunks: list[dict[str, Any]]   # top-k ranked chunks with scores
    retrieved_document_count: int | None     # total docs searched
    retrieval_latency_ms: int | None         # retrieval wall-clock time

    hyde_document: str | None               # hypothetical document (HyDE stage)

    retrieval_strategy: Literal[
        "dense",
        "hybrid",
        "rerank",
        "hyde",
    ] | None

    # ─────────────────────────────────────────────────────────────
    # Compressor  [Agent 4 — Team 3]
    # ─────────────────────────────────────────────────────────────

    compressed_context: str | None          # token-budget-trimmed context string
    token_count: int | None                 # total tokens in compressed context
    chunks: list[dict[str, Any]]            # chunked document segments
    chunk_strategy: Literal[
        "semantic",
        "hierarchical",
        "late",
    ] | None

    # ─────────────────────────────────────────────────────────────
    # Generation
    # ─────────────────────────────────────────────────────────────

    generated_answer: str | None            # LLM-generated answer

    llm_provider_used: Literal[
        "gemini-flash-3.5",
        "kimi-k2.6",
        "gemini-3.5",
    ] | None

    generation_latency_ms: int | None       # LLM generation wall-clock time

    # ─────────────────────────────────────────────────────────────
    # Evaluation  [Agent 5 — Team 2 — 3-layer stack]
    # ─────────────────────────────────────────────────────────────

    unified_score: float | None             # 0.0–1.0 composite deployment gate
                                            # formula: 0.25R + 0.35Q + 0.25F - 0.10L - 0.05C

    faithfulness: float | None              # RAGAS faithfulness — < 0.5 = hard block
    groundedness_score: float | None        # answer grounded in retrieved context
    relevance_score: float | None           # answer relevance to query

    ragas_metrics: dict[str, float] | None  # full RAGAS metric breakdown

    adversarial_pass_rate: float | None     # 1.0 = all 10 adversarial Q&A passed
    adversarial_pass: bool | None           # True if adversarial_pass_rate == 1.0

    adversarial_failures: list[dict[str, Any]]
    """
    Per-question failure detail, one entry per fabricated answer, e.g.:
    {"question_id": str, "hallucination_risk": str, "expected_behavior": str, "answer_snippet": str}
    Empty list when adversarial_pass_rate == 1.0 (no failures).
    """

    latency_p95_ms: int | None              # p95 query latency in milliseconds
    cost_per_query_usd: float | None        # estimated cost per query (USD)

    # ─────────────────────────────────────────────────────────────
    # Observation  [Agent 6 — Observer]
    # ─────────────────────────────────────────────────────────────

    error_rate: float | None                # rolling error rate (> 1% triggers rollback)

    quality_trend: Literal[
        "improving",
        "stable",
        "degrading",
    ] | None

    alert_triggered: bool | None            # True if any alert threshold breached

    observation_flags: dict[str, bool]
    """
    Per-threshold breach detail backing `alert_triggered`, e.g.:
    {"latency_breach": bool, "score_drop": bool, "error_spike": bool, "quality_drift": bool}
    """

    # ─────────────────────────────────────────────────────────────
    # Diagnosis  [Agent 7 — Diagnoser]
    # ─────────────────────────────────────────────────────────────

    failure_type: Literal[
        "F-01",   # Retrieval Miss — low recall
        "F-02",   # Context Overflow — truncated context
        "F-03",   # Hallucination — low faithfulness
        "F-04",   # Answer Incompleteness — low quality
        "F-05",   # Latency Spike — p95 > 3s
        "F-06",   # Quality Drift — sustained multi-run decline (G-6)
    ] | None

    failure_analysis: str | None            # detailed failure description
    confidence: float | None                # Diagnoser confidence in failure_type
    remediation_hint: str | None            # suggested fix for the Improver
    root_cause_analysis: str | None         # human-readable explanation

    retry_count: int                        # starts at 0 — incremented by observer
    max_retries: int                        # always 3 — never change at runtime

    # ─────────────────────────────────────────────────────────────
    # Improvement  [Agent 8 — Improver]
    # ─────────────────────────────────────────────────────────────

    variant_config: dict[str, Any] | None   # improved hyperparameter config delta
    variant_id: str | None                  # UUID v7 for the new pipeline variant
    improvement_attempt: int | None         # which improvement iteration (1-based)
    score_delta: float | None               # score improvement from last variant

    improver_candidates: list[dict[str, Any]]
    """
    All scored variants generated this attempt (not just the winner), e.g.:
    {"variant_id": str, "config": dict, "unified_score": float, "score_delta": float,
     "mlflow_run_id": str, "is_winner": bool}
    """

    # ─────────────────────────────────────────────────────────────
    # Human-in-the-Loop Gate
    # ─────────────────────────────────────────────────────────────

    approval_required: bool                 # True when 0.70 <= score < 0.85
    approval_status: str | None             # "pending" | "approved" | "rejected"
    approved_by: str | None                 # reviewer user_id
    approval_token: str | None              # signed approval token from HITL reviewer

    # ─────────────────────────────────────────────────────────────
    # Deployment  [Agent 9 — Deployer — Team 10]
    # ─────────────────────────────────────────────────────────────

    deployment_decision: str | None         # "deploy" | "rollback" | "skip"
    deploy_status: Literal[
        "success",
        "rolled_back",
        "failed",
    ] | None

    ecs_task_arn: str | None                # ECS task ARN for this deployment
    ecr_image_uri: str | None               # immutable SHA-tagged ECR image URI
    blue_task_arn: str | None               # currently live ECS task ARN
    green_task_arn: str | None              # new ECS task ARN being promoted
    active_task_arn: str | None             # ARN of the currently serving task
    rollback_reason: str | None             # populated if deploy_status == "rolled_back"

    # ─────────────────────────────────────────────────────────────
    # Safety & Guardrails  [blocks propagate across all nodes]
    # ─────────────────────────────────────────────────────────────

    guardrail_blocked: bool                 # If True — STOP. No output delivered.
                                            # See: ai-guardrails.md Rule 1

    guardrail_block_reason: Literal[
        "prompt_injection",
        "hallucination",
        "unsafe_output",
        "policy_violation",
        "pii_detected",
    ] | None


def format_pipeline_version(version_number: int) -> str:
    """Canonical string form of Pipeline.current_version for GraphState.pipeline_version.

    Version 4 (20-Jul-2026): every real dispatch site (evaluate.py,
    optimizer_service.py, retrieve.py, query.py) must use this exact format
    so pipeline_chunks' pipeline_version filter (migration 0016) actually
    matches the rows a given version's ingestion wrote -- an inconsistent
    format between the writer and a reader is an exact-string-match miss,
    not a sanitized-identical-identifier like the old per-table convention.
    """
    return f"v{version_number}"


def initial_state(
    *,
    run_id: str,
    pipeline_id: str,
    organization_id: str,
    x_trace_id: str,
    user_id: str,
    session_id: str,
    raw_query: str = "",
    pipeline_version: str = "v1",
    deployment_id: str | None = None,
    variant_config: dict | None = None,
) -> GraphState:
    """Factory — creates a clean GraphState for a new pipeline run.

    All identity fields are keyword-only to prevent positional argument mistakes.
    Sets created_at and updated_at to current UTC time.
    Sets retry_count=0, max_retries=3, guardrail_blocked=False as safe defaults.

    variant_config (20-Jul-2026, Apply Improvement feature): pre-seeds the
    field ingestion_node already reads chunk_strategy from
    (app/graph/nodes/ingestion.py) and builder_node already reads retrieval
    params from (app/graph/nodes/builder.py) -- this lets a caller dispatch a
    run against a specific config (e.g. an Improver-recommended variant)
    without any GraphState schema change; `variant_config` already exists as
    a field, this just gives callers other than improver_node a way to
    populate it before dispatch.
    """
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return GraphState(
        graph_state_version="v1.0",
        run_id=run_id,
        pipeline_id=pipeline_id,
        pipeline_version=pipeline_version,
        organization_id=organization_id,
        x_trace_id=x_trace_id,
        user_id=user_id,
        session_id=session_id,
        created_at=now,
        updated_at=now,
        deployment_id=deployment_id,
        execution_trace=[],
        raw_query=raw_query,
        rewritten_query=None,
        query_embedding=None,
        retrieved_chunks=[],
        retrieved_document_count=None,
        retrieval_latency_ms=None,
        retrieval_strategy=None,
        hyde_document=None,
        compressed_context=None,
        token_count=None,
        chunks=[],
        chunk_strategy=None,
        generated_answer=None,
        llm_provider_used=None,
        generation_latency_ms=None,
        unified_score=None,
        faithfulness=None,
        groundedness_score=None,
        relevance_score=None,
        ragas_metrics=None,
        adversarial_pass_rate=None,
        adversarial_pass=None,
        adversarial_failures=[],
        latency_p95_ms=None,
        cost_per_query_usd=None,
        error_rate=None,
        quality_trend=None,
        alert_triggered=None,
        observation_flags={},
        failure_type=None,
        failure_analysis=None,
        confidence=None,
        remediation_hint=None,
        root_cause_analysis=None,
        retry_count=0,
        max_retries=3,
        variant_config=variant_config,
        variant_id=None,
        improvement_attempt=None,
        score_delta=None,
        approval_required=False,
        approval_status=None,
        approved_by=None,
        approval_token=None,
        deployment_decision=None,
        deploy_status=None,
        ecs_task_arn=None,
        ecr_image_uri=None,
        blue_task_arn=None,
        green_task_arn=None,
        active_task_arn=None,
        rollback_reason=None,
        guardrail_blocked=False,
        guardrail_block_reason=None,
    )

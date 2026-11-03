"""Backward-compatible shim — canonical ORM models live in :mod:`app.models`.

Kept so legacy imports (``from app.db.models import Organization``) resolve to
the single canonical model set. Do **not** add new models here; add them to
:mod:`app.models` instead so they register on one shared ``Base.metadata``.
"""

from app.models import (
    AuditLog,
    Deployment,
    EvaluationRun,
    ExperimentRun,
    Organization,
    Pipeline,
    PipelineVersion,
    RetrievalChunk,
    User,
)

__all__ = [
    "Organization",
    "User",
    "Pipeline",
    "PipelineVersion",
    "EvaluationRun",
    "RetrievalChunk",
    "ExperimentRun",
    "Deployment",
    "AuditLog",
]

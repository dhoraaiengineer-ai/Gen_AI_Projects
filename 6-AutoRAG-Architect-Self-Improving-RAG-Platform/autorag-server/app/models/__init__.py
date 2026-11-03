"""SQLAlchemy ORM models for AutoRAG Architect v3.0.

Import order follows FK dependency chain:
  Organization → User → Pipeline → PipelineVersion → Document
  → EvaluationRun → RetrievalChunk → ExperimentRun → Deployment → AuditLog

All models share Base from app.models.base.
Alembic env.py imports Base.metadata for autogenerate.
"""

from app.models.audit_log import APPROVED_EVENT_TYPES, AuditLog
from app.models.base import Base, uuid7
from app.models.batch_evaluation import BatchEvaluation, BatchRun
from app.models.deployment import Deployment
from app.models.document import Document
from app.models.evaluation_config import EvaluationConfig
from app.models.evaluation_dataset import (
    EvaluationDataset,
    EvaluationDatasetVersion,
    GoldenQuestion,
)
from app.models.evaluation_run import EvaluationRun
from app.models.experiment_run import ExperimentRun
from app.models.organization import Organization
from app.models.pipeline import Pipeline
from app.models.pipeline_version import PipelineVersion
from app.models.retrieval_chunk import RetrievalChunk
from app.models.user import User

__all__ = [
    "Base",
    "uuid7",
    "Organization",
    "User",
    "Pipeline",
    "PipelineVersion",
    "Document",
    "EvaluationRun",
    "RetrievalChunk",
    "ExperimentRun",
    "Deployment",
    "AuditLog",
    "APPROVED_EVENT_TYPES",
    "EvaluationDataset",
    "EvaluationDatasetVersion",
    "GoldenQuestion",
    "EvaluationConfig",
    "BatchRun",
    "BatchEvaluation",
]

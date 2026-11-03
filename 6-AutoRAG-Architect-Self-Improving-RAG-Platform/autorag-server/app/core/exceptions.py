"""Domain-specific exceptions for AutoRAG Architect."""


class AutoRAGError(Exception):
    """Base exception for all AutoRAG errors."""


class DeploymentBlockedError(AutoRAGError):
    """Raised when Unified Score < 0.85 or faithfulness < 0.5 blocks deployment."""

    def __init__(self, reason: str, score: float = 0.0) -> None:
        self.reason = reason
        self.score = score
        super().__init__(f"Deployment blocked: {reason} (score={score})")


class GuardrailBlockedError(AutoRAGError):
    """Raised when a guardrail layer blocks a request."""

    def __init__(self, reason: str, trace_id: str = "", detail: str = "") -> None:
        self.reason = reason
        self.trace_id = trace_id
        self.detail = detail
        super().__init__(f"Guardrail blocked [{reason}]: {detail}")


class PipelineNotFoundError(AutoRAGError):
    """Raised when a pipeline_id does not exist for the given organization."""


class PipelineNameExistsError(AutoRAGError):
    """Raised when creating a pipeline whose name already exists for the org.

    26-Jul-2026 fix (P0 UAT finding): the `uq_pipelines_org_name` unique
    constraint previously surfaced as an unhandled asyncpg.UniqueViolationError
    -> sqlalchemy.exc.IntegrityError, which crashed the request without a clean
    HTTP response. The browser observed this as a bare "TypeError: Failed to
    fetch" / net::ERR_FAILED with no useful detail -- confirmed via a live
    repro correlating browser-side fetch exception timestamps against the
    backend's own traceback log. This exception lets the route return the
    standard {"status":"error",...} envelope instead.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"A pipeline named '{name}' already exists in this organization.")


class EvaluationDatasetNotFoundError(AutoRAGError):
    """Raised when a dataset/version/golden-question id does not exist for the given organization."""


class DatasetVersionNotPublishedError(AutoRAGError):
    """Raised when a batch run is requested against a dataset version whose
    lifecycle_status is not 'published' (still draft/under_review/archived)."""

    def __init__(self, version_id: str, lifecycle_status: str) -> None:
        self.version_id = version_id
        self.lifecycle_status = lifecycle_status
        super().__init__(
            f"Dataset version {version_id} is '{lifecycle_status}', not 'published' "
            "-- only published versions are selectable for a batch run."
        )


class BatchRunNotFoundError(AutoRAGError):
    """Raised when a batch_run_id does not exist for the given organization."""


class EmptyDatasetVersionError(AutoRAGError):
    """Raised when start_batch_run is called against a dataset version with
    zero 'approved' golden questions -- there is nothing to dispatch."""

    def __init__(self, version_id: str) -> None:
        self.version_id = version_id
        super().__init__(
            f"Dataset version {version_id} has no approved golden questions to run."
        )


class EvaluationFailedError(AutoRAGError):
    """Raised when the Evaluator agent cannot complete scoring."""


class LLMProviderError(AutoRAGError):
    """Raised when all LLM providers in the failover chain are unavailable."""

    def __init__(self, message: str, x_trace_id: str = "") -> None:
        self.x_trace_id = x_trace_id
        super().__init__(message)


class CostLimitExceeded(AutoRAGError):  # noqa: N818 — domain name; Error suffix intentionally omitted
    """Raised by CostGuardrail when a call would exceed the configured budget."""

    def __init__(self, context: str, cost_usd: float, budget_usd: float) -> None:
        self.context = context
        self.cost_usd = cost_usd
        self.budget_usd = budget_usd
        super().__init__(
            f"Cost limit exceeded [{context}]: "
            f"${cost_usd:.6f} > budget ${budget_usd:.2f}"
        )


class TokenLimitExceeded(AutoRAGError):  # noqa: N818 — domain name; Error suffix intentionally omitted
    """Raised by TokenGuardrail when token count exceeds the configured budget."""

    def __init__(
        self, token_type: str, count: int, limit: int, context: str = ""
    ) -> None:
        self.token_type = token_type
        self.count = count
        self.limit = limit
        super().__init__(
            f"Token limit exceeded [{token_type}]: {count} > {limit}"
            + (f" ({context})" if context else "")
        )

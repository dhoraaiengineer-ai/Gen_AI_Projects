"""LLM gateway: the single entry point for every chat-model call.

- Routing: each task (triage, scope, rewrite, rerank, judge, answer, eval_judge) is sent to a route
  ("fast" or "quality"), and each route is a fallback model chain with circuit breakers.
- Token limits: the requested output budget is clamped to the task's [min, max] (reasoning models return
  nothing when max_tokens is tiny), and the estimated prompt size must fit the task's input budget.
- Accounting: estimated prompt tokens per task, real provider usage per task/model (providers.py), and
  budget events. Labels are task/model enums only; no prompt text is ever logged.

Policy lives in llm_gateway.yaml. Callers keep the ChatModel interface: `gateway.for_task("scope")`.
"""

from __future__ import annotations

import contextvars
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from app.core.errors import AppError
from app.core.metrics import PROMPT_TOKENS, TOKEN_BUDGET_EVENTS
from app.rag.interfaces import ChatModel

logger = logging.getLogger(__name__)

POLICY_PATH = Path(__file__).with_name("llm_gateway.yaml")
Route = Literal["fast", "quality"]
ROUTES: tuple[Route, ...] = ("fast", "quality")

# The task of the model call in progress; providers.py reads it to label real token usage.
current_task: contextvars.ContextVar[str] = contextvars.ContextVar("llm_task", default="unknown")


class TokenBudgetExceededError(AppError):
    """The prompt does not fit the task's input budget. Handled like a failed model call."""

    status_code = 422
    public_message = "The request is too large to process. Please shorten it."


@dataclass(frozen=True)
class TaskProfile:
    route: Route
    min_output_tokens: int
    max_output_tokens: int
    max_input_tokens: int

    def clamp_output(self, requested: int | None) -> int:
        wanted = requested if requested is not None else self.max_output_tokens
        return max(self.min_output_tokens, min(wanted, self.max_output_tokens))


@dataclass(frozen=True)
class GatewayPolicy:
    chars_per_token: int
    tasks: dict[str, TaskProfile]

    @classmethod
    def load(cls, path: Path = POLICY_PATH) -> GatewayPolicy:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        tasks: dict[str, TaskProfile] = {}
        for name, spec in raw["tasks"].items():
            profile = TaskProfile(
                route=spec["route"],
                min_output_tokens=int(spec["min_output_tokens"]),
                max_output_tokens=int(spec["max_output_tokens"]),
                max_input_tokens=int(spec["max_input_tokens"]),
            )
            if profile.route not in ROUTES:
                raise ValueError(f"task {name!r}: unknown route {profile.route!r}")
            if not 0 < profile.min_output_tokens <= profile.max_output_tokens:
                raise ValueError(f"task {name!r}: need 0 < min_output_tokens <= max_output_tokens")
            if profile.max_input_tokens <= 0:
                raise ValueError(f"task {name!r}: max_input_tokens must be positive")
            tasks[name] = profile
        chars = int(raw.get("chars_per_token", 4))
        if chars <= 0:
            raise ValueError("chars_per_token must be positive")
        return cls(chars_per_token=chars, tasks=tasks)

    def estimate_tokens(self, *texts: str) -> int:
        """Conservative offline estimate (no tokenizer download)."""
        return sum(math.ceil(len(t) / self.chars_per_token) for t in texts)


class TaskModel:
    """A ChatModel bound to one task: routes, clamps the output budget, checks the input budget."""

    def __init__(self, task: str, profile: TaskProfile, model: ChatModel, policy: GatewayPolicy) -> None:
        self.task = task
        self.profile = profile
        self._model = model
        self._policy = policy
        self.name = model.name

    def fits(self, system: str, user: str) -> bool:
        return self._policy.estimate_tokens(system, user) <= self.profile.max_input_tokens

    def complete(self, system: str, user: str, *, temperature: float, max_tokens: int | None = None) -> str:
        prompt_tokens = self._policy.estimate_tokens(system, user)
        PROMPT_TOKENS.labels(self.task).observe(prompt_tokens)
        if prompt_tokens > self.profile.max_input_tokens:
            TOKEN_BUDGET_EVENTS.labels(self.task, "input_rejected").inc()
            logger.warning(
                "prompt over the task input budget; call not made",
                extra={"task": self.task, "tokens": prompt_tokens, "budget": self.profile.max_input_tokens},
            )
            raise TokenBudgetExceededError()
        out_tokens = self.profile.clamp_output(max_tokens)
        if max_tokens is not None and out_tokens != max_tokens:
            TOKEN_BUDGET_EVENTS.labels(self.task, "output_clamped").inc()
        token = current_task.set(self.task)
        try:
            return self._model.complete(system, user, temperature=temperature, max_tokens=out_tokens)
        finally:
            current_task.reset(token)


class LLMGateway:
    def __init__(self, routes: dict[Route, ChatModel], policy: GatewayPolicy | None = None) -> None:
        missing = [r for r in ROUTES if r not in routes]
        if missing:
            raise ValueError(f"missing routes: {missing}")
        self._routes = routes
        self.policy = policy or GatewayPolicy.load()

    def for_task(self, task: str) -> TaskModel:
        try:
            profile = self.policy.tasks[task]
        except KeyError as exc:
            raise ValueError(f"no gateway policy for task {task!r}") from exc
        return TaskModel(task, profile, self._routes[profile.route], self.policy)

    def describe(self) -> list[dict[str, object]]:
        """Routing table for docs/ops (model names and limits only)."""
        return [
            {
                "task": name,
                "route": p.route,
                "model": self._routes[p.route].name,
                "min_output_tokens": p.min_output_tokens,
                "max_output_tokens": p.max_output_tokens,
                "max_input_tokens": p.max_input_tokens,
            }
            for name, p in self.policy.tasks.items()
        ]

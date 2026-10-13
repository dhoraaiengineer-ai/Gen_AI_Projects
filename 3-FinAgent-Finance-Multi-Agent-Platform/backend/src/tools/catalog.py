"""Assemble every tool into a registry."""

from __future__ import annotations

from src.tools import finance, knowledge, market, ml, portfolio, research, risk
from src.tools.base import ToolCallRecorder
from src.tools.deps import ToolDeps
from src.tools.registry import ToolRegistry


def build_registry(deps: ToolDeps, recorder: ToolCallRecorder | None = None) -> ToolRegistry:
    registry = ToolRegistry(recorder)
    for module in (market, finance, risk, portfolio, research, ml, knowledge):
        registry.register_all(module.build(deps))
    return registry

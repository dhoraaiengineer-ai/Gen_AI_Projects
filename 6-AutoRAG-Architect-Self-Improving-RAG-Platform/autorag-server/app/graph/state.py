"""Backward-compatibility re-export shim.

The authoritative GraphState definition has moved to app.core.state.
All imports from app.graph.state continue to work unchanged.

New code should import directly from app.core.state:
    from app.core.state import GraphState, initial_state
"""

from app.core.state import GraphState, initial_state  # noqa: F401

__all__ = ["GraphState", "initial_state"]

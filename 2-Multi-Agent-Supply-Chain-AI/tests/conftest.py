"""Shared test configuration.

Tests run offline: they never read `.env` and never call real services. Tests marked `integration`
or `live` are skipped unless RUN_INTEGRATION=1 / RUN_LIVE=1.
"""

import os

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    gates = {"integration": "RUN_INTEGRATION", "live": "RUN_LIVE"}
    for item in items:
        for marker, env_var in gates.items():
            if marker in item.keywords and os.environ.get(env_var) != "1":
                item.add_marker(pytest.mark.skip(reason=f"set {env_var}=1 to run {marker} tests"))

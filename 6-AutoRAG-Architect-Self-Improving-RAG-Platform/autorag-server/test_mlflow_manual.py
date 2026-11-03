"""Manual test to verify MLflow logging works for the Improver node.

Run from autorag-server/:
    source .venv/bin/activate
    python3 test_mlflow_manual.py

MLflow UI must be running at http://localhost:5000 before you run this.
Start it with: mlflow ui --port 5000
"""

import asyncio
import os
import sys

sys.path.insert(0, ".")
os.environ["MLFLOW_TRACKING_URI"] = "http://localhost:5000"

from app.core.state import initial_state
from app.graph.nodes.improver import improver_node


async def run_test(failure_type: str, score: float) -> None:
    print(f"\n--- Testing failure_type={failure_type}, unified_score={score} ---")

    state = initial_state(
        run_id="test-run-001",
        pipeline_id="test-pipeline-001",
        organization_id="test-org-001",
        x_trace_id="trace-abc-123",
    )
    state["failure_type"] = failure_type
    state["unified_score"] = score

    result = await improver_node(state)

    print(f"  variant_id  : {result['variant_id']}")
    print(f"  best config : {result['variant_config']}")
    print(f"  trace nodes : {[e['node'] for e in result['execution_trace']]}")
    print(f"  status      : {result['execution_trace'][-1]['status']}")


async def main() -> None:
    print("Starting MLflow logging test...")
    print("Make sure MLflow UI is running: mlflow ui --port 5000")
    print("Then open: http://localhost:5000\n")

    # Test all 5 failure types
    await run_test("F-01", 0.62)  # Retrieval Miss
    await run_test("F-02", 0.58)  # Context Overflow
    await run_test("F-03", 0.55)  # Hallucination
    await run_test("F-04", 0.60)  # Answer Incompleteness
    await run_test("F-05", 0.65)  # Latency Spike

    print("\n✅ All tests done.")
    print("Go to http://localhost:5000 and look for experiment: autorag-pipeline-test-pipeline-001")
    print("You should see 15 runs (3 variants × 5 failure types).")


asyncio.run(main())

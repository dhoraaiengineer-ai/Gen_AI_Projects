# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 10-Jul-2026 (IST)

---

# Rule 60: AutoRAG Agents

## Enforces:

1. **Orchestration**: Mandatory **LangGraph** state machine (explicit nodes and conditional edges).
   - Graph: `autorag-server/app/core/workflow.py` → `build_autorag_graph()`
   - Entry point: `ingestion` node
   - All 9 nodes defined in `app/graph/nodes/` (one file per agent)

2. **State**: All agent nodes read from and write to `GraphState` **only**.
   - Authoritative import: `from app.core.state import GraphState`
   - Shim (backward compat): `from app.graph.state import GraphState` (re-exports from above)
   - `initial_state()` factory: `from app.core.state import initial_state`
   - Nodes must NEVER store mutable state outside `GraphState`

3. **Persistence**: `PostgresSaver` for in-flight state checkpointing (wired in P6-2).
   - Every node completion saves `GraphState` to Supabase PostgreSQL `checkpoints` table
   - Enables crash recovery and mid-run resume

4. **Node Pattern**: Every agent node must follow:
   ```python
   async def my_node(state: GraphState) -> GraphState:
       # 1. Read only owned input fields
       # 2. PII-mask all data before any write
       # 3. Execute agent logic
       # 4. Write only owned output fields
       # 5. Append to execution_trace
       return {**state, "my_field": result}
   ```
   - Must be `async def`
   - Must log `x_trace_id` in every structured log line
   - Must mask PII before any write to `GraphState` or Supabase

5. **Loop Logic**: The autonomous improvement cycle must follow explicit edges:
   ```
   observer → diagnoser → improver → ingestion (loop)
   ```
   - `_route_after_observer()` in `app/core/workflow.py` controls retry vs END
   - Maximum 3 retries (`retry_count >= 3` → END)

6. **Failover**: Mandatory LLM chain (reflected in `state.llm_provider_used`):
   ```
   Gemini Flash 3.5 → KiMi K2.6 → Gemini 3.5
   ```

## Anti-Patterns:

- Standalone async tasks that bypass the LangGraph graph for agent logic
- Hard-coded next-step logic inside an agent instead of using graph edges (workflow-contracts.md Rule 3)
- Unmasked PII entering `GraphState` (graph-state-governance.md Rule 6)
- Inline `try/except` retry loops inside node functions — retries must be explicit graph edges (Rule 4 enforcement)
- Importing `GraphState` from anywhere other than `app.core.state` or the shim `app.graph.state`
- Writing to fields owned by another agent (see ownership map in `docs/ARCHITECTURE.md`)

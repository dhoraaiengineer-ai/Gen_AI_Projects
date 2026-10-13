"""Report agent: deterministic executive report built from agent facts.

Layout, numbers and recommendations come from code; the only LLM text is the validated
interpretation paragraph. Sections follow the financial-safety contract: FACT · ML PREDICTION ·
LLM INTERPRETATION · RECOMMENDATION · ASSUMPTION · UNCERTAINTY.
"""

from __future__ import annotations

from typing import Any

from src.agents.base import pct, pct_exact

DISCLAIMER = "Decision support only — not investment advice. No orders are executed automatically."
OUT_OF_SCOPE = (
    "I can help with portfolio, market, risk, fraud, research and compliance questions for your "
    "firm. That question is outside what FinAgent covers."
)

ML_PREFIX = "ML PREDICTION:"


def _risk_level(results: dict[str, dict[str, Any]]) -> str | None:
    category = results.get("risk", {}).get("extra", {}).get("riskCategory")
    return str(category) if category else None


def headline(intent: str, portfolio: str | None, results: dict[str, dict[str, Any]]) -> str:
    risk = results.get("risk", {}).get("extra", {})
    compliance = results.get("compliance", {}).get("extra", {})
    portfolio_extra = results.get("portfolio", {}).get("extra", {})
    name = portfolio_extra.get("portfolio", {}).get("name") or portfolio or "The portfolio"
    parts: list[str] = []
    if risk.get("riskCategory"):
        parts.append(f"{name}: risk {risk['riskCategory']} ({risk.get('riskScore', 0):.0f}/100)")
    change = risk.get("riskChange")
    if change:
        driver = (
            "market moves"
            if change["marketEffect"] >= change["weightsEffect"]
            else "position changes"
        )
        parts.append(
            f"volatility {pct(change['volatilityBefore'])} → {pct(change['volatilityAfter'])}, "
            f"driven mainly by {driver}"
        )
    hard = compliance.get("hardBreaches") or []
    if hard:
        first = hard[0]
        parts.append(f"{len(hard)} hard limit breach ({first['subject']} {pct(first['actual'])})")
    if not parts:
        if intent == "market_overview":
            return "Market overview"
        return f"{name}: summary"
    text = "; ".join(parts) + "."
    return text if text.startswith(name) else f"{name}: {text}"


def recommendations(results: dict[str, dict[str, Any]]) -> list[str]:
    recs: list[str] = []
    compliance = results.get("compliance", {}).get("extra", {})
    for breach in compliance.get("hardBreaches") or []:
        if breach["limitType"] == "single_name":
            recs.append(
                f"Bring {breach['subject']} back below the {pct_exact(breach['threshold'])} single-name "
                "limit; a draft rebalance can be prepared and needs portfolio-manager or compliance approval."
            )
    for breach in compliance.get("warningBreaches") or []:
        if breach["limitType"] == "sector":
            recs.append(
                f"Review {breach['subject']} exposure ({pct(breach['actual'])} vs "
                f"{pct_exact(breach['threshold'])} warning limit)."
            )
        elif breach["limitType"] == "var_95_1d":
            recs.append(
                f"1-day VaR ({pct(breach['actual'], 2)}) is above the {pct_exact(breach['threshold'])} budget; "
                "consider reducing the most volatile positions."
            )
    return recs


def build_report(state: dict[str, Any]) -> dict[str, Any]:
    results: dict[str, dict[str, Any]] = state.get("agent_results", {})
    intent = state.get("intent", "")
    lines = [
        {"agent": a, "text": h}
        for a, r in results.items()
        for h in r.get("highlights", [])
        if not h.startswith("Decision support only")
    ]
    # FACT vs ML PREDICTION are separate sections (financial safety rules).
    facts = [f for f in lines if not f["text"].startswith(ML_PREFIX)]
    ml_predictions = [
        {"agent": f["agent"], "text": f["text"].removeprefix(ML_PREFIX).strip()}
        for f in lines
        if f["text"].startswith(ML_PREFIX)
    ]
    uncertainty = [f"{a}: {e}" for a, r in results.items() for e in r.get("errors", [])]
    uncertainty += [
        f"{a} agent finished with status {r['status']}"
        for a, r in results.items()
        if r.get("status") not in ("ok", None)
    ]
    if state.get("validation", {}).get("ungrounded"):
        uncertainty.append(
            "The model's narrative contained numbers not found in the tool results; "
            "a deterministic summary is shown instead."
        )
    portfolio_extra = results.get("portfolio", {}).get("extra", {})
    compliance = results.get("compliance", {}).get("extra", {})
    confidences = [float(r.get("confidence", 0)) for r in results.values()]
    evidence = [e for r in results.values() for e in r.get("evidence", [])]
    return {
        "requestId": state.get("request_id"),
        "question": state.get("question"),
        "intent": intent,
        "portfolio": state.get("portfolio_id"),
        "tickers": list(state.get("tickers") or []),
        "headline": headline(intent, state.get("portfolio_id"), results),
        "riskLevel": _risk_level(results),
        "sections": {
            "facts": facts,
            "mlPredictions": ml_predictions,
            "interpretation": state.get("guard_message")
            or (OUT_OF_SCOPE if intent == "out_of_scope" else state.get("narrative")),
            "interpretationSource": state.get("narrative_source", "deterministic"),
            "recommendations": recommendations(results),
            "assumptions": list(dict.fromkeys(state.get("assumptions", []))),
            "uncertainty": uncertainty,
        },
        "holdings": (portfolio_extra.get("holdings") or [])[:10],
        "breaches": (compliance.get("hardBreaches") or [])
        + (compliance.get("warningBreaches") or []),
        "approval": {
            "required": bool(compliance.get("approvalRequired")),
            "reasons": compliance.get("approvalReasons") or [],
        },
        "agents": [
            {
                "name": a,
                "status": r.get("status"),
                "confidence": r.get("confidence"),
                "durationMs": r.get("duration_ms"),
                "llmUsed": r.get("llm_used"),
                "toolCalls": [c["tool"] for c in r.get("tool_calls", [])],
            }
            for a, r in results.items()
        ],
        "evidence": evidence,
        "confidence": round(min(confidences), 2) if confidences else 0.0,
        "routing": state.get("classification", {}),
        "guard": {
            "input": "blocked" if state.get("blocked") else "passed",
            "reason": state.get("guard_reason"),
            "flags": sorted(set(state.get("guard_flags", []))),
            "output": "flagged"
            if state.get("validation", {}).get("ungrounded")
            or state.get("validation", {}).get("output")
            else "grounded",
        },
        "disclaimer": DISCLAIMER,
    }

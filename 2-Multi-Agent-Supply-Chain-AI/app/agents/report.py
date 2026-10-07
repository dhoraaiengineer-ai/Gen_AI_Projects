"""Deterministic report construction. Headline, evidence, supplier, impact and approval come from tool data;
the LLM contributes only the streamed narrative summary (validated against these facts)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.guardrails.pipeline import OUT_OF_SCOPE_MESSAGE


def approval_id_for(run_id: str) -> str:
    return f"APR-{run_id.replace('-', '')[-8:].upper()}"


def facts_for(state: dict[str, Any]) -> dict[str, Any]:
    """Compact, LLM-safe facts used for synthesis and for grounding validation."""
    facts: dict[str, Any] = {}
    if inv := state.get("inventory_data"):
        facts["inventory"] = {
            k: inv.get(k)
            for k in (
                "sku",
                "name",
                "available",
                "on_hand",
                "on_order",
                "forecast_30d",
                "safety_stock",
                "reorder_point",
                "reorder_qty",
                "days_of_cover",
                "lead_time_days",
                "risk",
            )
            if k in inv
        }
        if inv.get("at_risk"):
            facts["at_risk"] = inv["at_risk"][:8]
    if fc := state.get("demand_forecast"):
        facts["demand"] = {k: fc.get(k) for k in ("sku", "total", "daily_mean", "trend", "mape_pct", "confidence", "method")}
    if sup := state.get("supplier_data"):
        rec = sup.get("recommended") or {}
        facts["supplier"] = {
            "recommended": rec,
            "reasons": sup.get("reasons", []),
            "compared": [
                {k: r[k] for k in ("name", "unit_price", "lead_time_days", "reliability", "eligible")} for r in sup.get("ranked", [])
            ],
        }
    if log := state.get("logistics_data"):
        facts["logistics"] = {"delayed_count": log.get("delayed_count"), "shipments": log.get("shipments", [])[:8]}
    if appr := state.get("approval"):
        facts["approval"] = {"value": appr.get("value"), "threshold": appr.get("threshold")}
    return facts


def evidence_text(state: dict[str, Any]) -> str:
    docs = "\n".join(d.get("text", "") for d in state.get("retrieved_documents", []))
    return json.dumps(facts_for(state), default=str) + "\n" + docs


def _sources(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"n": d["n"], "title": d["source"], "location": d["location"]} for d in state.get("retrieved_documents", [])]


def _agents(state: dict[str, Any]) -> list[str]:
    return ["supervisor", *[a for stage in state.get("plan", []) for a in stage]]


def _confidence(state: dict[str, Any], base: float) -> dict[str, Any]:
    penalty = 0.08 * len([e for e in state.get("errors", []) if e.get("error") not in {"llm_unavailable"}])
    score = max(0.3, round(base - penalty, 2))
    return {"level": "high" if score >= 0.85 else "medium" if score >= 0.65 else "low", "score": score}


def build_report(state: dict[str, Any], *, approval_threshold: float, approval_ttl_hours: int) -> dict[str, Any]:  # noqa: PLR0912, PLR0915
    intent = state.get("intent", "out_of_scope")
    inv = state.get("inventory_data") or {}
    fc = state.get("demand_forecast") or {}
    sup = state.get("supplier_data") or {}
    log = state.get("logistics_data") or {}
    notes = state.get("agent_notes", {})
    report: dict[str, Any] = {
        "headline": "",
        "riskLevel": "low",
        "summary": "",
        "reasoning": [],
        "evidence": [],
        "impact": [],
        "confidence": _confidence(state, 0.9),
        "sources": _sources(state),
        "agentsInvolved": _agents(state),
        "guard": {"status": "grounded", "reasons": []},
        "latencyMs": 0,
        "requestId": state.get("request_id", ""),
    }
    sku = (state.get("skus") or [None])[0]

    if intent == "out_of_scope" or state.get("blocked"):
        report.update(
            headline="That's outside what I can help with" if intent == "out_of_scope" else "Request not processed",
            summary=state.get("block_message") or OUT_OF_SCOPE_MESSAGE,
            agentsInvolved=["supervisor"],
        )
        return report

    if inv.get("not_found") or (
        intent in {"reorder_quantity", "full_recommendation", "inventory_explanation"} and sku and not inv.get("sku") and not fc.get("sku")
    ):
        report.update(
            headline=f"I couldn't find {sku}",
            summary=f"{sku} doesn't exist in the product catalogue. Check the SKU, or ask which products are at risk.",
            confidence={"level": "high", "score": 0.95},
        )
        return report

    evidence: list[dict[str, Any]] = []
    if inv.get("sku"):
        evidence += [
            {"label": "Available stock", "value": f"{inv['available']:,} units", "source": "inventory"},
            {"label": "30-day forecast", "value": f"{inv.get('forecast_30d', fc.get('total', 0)):,} units", "source": "demand"},
            {"label": "Days of cover", "value": f"{inv['days_of_cover']} days", "source": "inventory"},
            {
                "label": "Safety stock / ROP",
                "value": f"{inv.get('safety_stock', 0):,} / {inv.get('reorder_point', 0):,}",
                "source": "inventory",
            },
        ]
    reasoning = [n for a in ("demand", "inventory", "supplier", "logistics", "rag", "research") if (n := notes.get(a))]

    if intent == "stockout_risk":
        items = inv.get("at_risk", [])
        crit = [i for i in items if i["risk"] == "critical"]
        report.update(
            headline=f"{len(items)} products need attention — {len(crit)} at critical stockout risk"
            if items
            else "No products are at risk of stockout",
            riskLevel="critical" if crit else "high" if items else "low",
            reasoning=reasoning or ["Risk compares days of cover with supplier lead time and the reorder point"],
            evidence=[
                {"label": "Critical SKUs", "value": str(len(crit)), "source": "inventory"},
                {"label": "High-risk SKUs", "value": str(len(items) - len(crit)), "source": "inventory"},
            ],
            table={
                "title": "Highest-risk products",
                "columns": ["SKU", "Product", "Days of cover", "Lead time", "Risk", "Suggested reorder"],
                "rows": [
                    [i["sku"], i["name"], i["days_of_cover"], f"{i['lead_time_days']} d", i["risk"].upper(), f"{i['reorder_qty']:,}"]
                    for i in items[:10]
                ],
            },
            impact=["Prioritised reorder list ready for review"] if items else [],
        )
        return report

    if intent == "shipment_status":
        ships = log.get("shipments", [])
        avg = sum(s["delay_days"] for s in ships) / len(ships) if ships else 0
        report.update(
            headline=f"{len(ships)} shipments are delayed — average {avg:.1f} days" if ships else "No delayed shipments",
            riskLevel="high" if ships else "low",
            reasoning=reasoning,
            evidence=[
                {"label": "Delayed shipments", "value": str(len(ships)), "source": "logistics"},
                {"label": "Average delay", "value": f"{avg:.1f} days", "source": "logistics"},
            ],
            table={
                "title": "Delayed shipments",
                "columns": ["Shipment", "SKU", "Carrier", "Route", "Delay", "Latest event"],
                "rows": [[s["shipment_id"], s["sku"], s["carrier"], s["route"], f"{s['delay_days']} d", s["last_event"]] for s in ships],
            },
        )
        return report

    if intent in {"policy_question", "research"}:
        docs = state.get("retrieved_documents", [])
        report.update(
            headline="Here's what your documents say" if docs else "I couldn't find that in your documents",
            reasoning=[],
            confidence={"level": "high" if docs else "low", "score": 0.9 if docs else 0.3},
        )
        if intent == "research" and state.get("research_data", {}).get("web_sources"):
            report["webSources"] = state["research_data"]["web_sources"]
        return report

    if intent == "demand_forecast" and fc:
        report.update(
            headline=f"{fc.get('sku')} demand forecast: {fc.get('total', 0):,} units over the next {fc.get('horizon_days', 30)} days",
            reasoning=fc.get("drivers", []) or reasoning,
            evidence=[
                {"label": "30-day forecast", "value": f"{fc.get('total', 0):,} units", "source": "demand"},
                {"label": "Daily mean", "value": f"{fc.get('daily_mean')} units", "source": "demand"},
                {"label": "Method", "value": fc.get("method", ""), "source": "demand"},
                {"label": "MAPE (backtest)", "value": f"{fc.get('mape_pct')}%", "source": "demand"},
            ],
            confidence={"level": fc.get("confidence", "medium"), "score": round(1 - (fc.get("mape_pct") or 15) / 100, 2)},
        )
        return report

    risk = inv.get("risk", "low")
    rec = sup.get("recommended") or {}
    if intent == "supplier_selection" and rec:
        report.update(
            headline=f"Select {rec['name']} for {sku}",
            riskLevel=risk,
            reasoning=sup.get("reasons", []) + reasoning,
            evidence=[
                {
                    "label": r["name"],
                    "value": f"${r['unit_price']:.2f} · {r['lead_time_days']} d · {r['reliability'] * 100:.0f}%",
                    "source": "supplier",
                }
                for r in sup.get("ranked", [])
            ],
            supplier={
                "id": rec["supplier_id"],
                "name": rec["name"],
                "unitPrice": rec["unit_price"],
                "leadTimeDays": rec["lead_time_days"],
                "reliability": rec["reliability"],
            },
        )
        return report

    if intent == "inventory_explanation":
        report.update(
            headline=f"Why {sku} inventory is {'low' if risk in {'critical', 'high'} else 'at its current level'}",
            riskLevel=risk,
            reasoning=reasoning,
            evidence=evidence,
            impact=[f"Reordering {inv.get('reorder_qty', 0):,} units restores cover above the reorder point"]
            if inv.get("reorder_qty")
            else [],
        )
        return report

    # reorder_quantity / full_recommendation
    qty = int(inv.get("reorder_qty") or 0)
    report.update(riskLevel=risk, reasoning=reasoning, evidence=evidence)
    if qty <= 0:
        report.update(headline=f"No reorder needed for {sku}", impact=["Stock and inbound supply cover forecast demand"])
        return report
    if rec:
        report["supplier"] = {
            "id": rec["supplier_id"],
            "name": rec["name"],
            "unitPrice": rec["unit_price"],
            "leadTimeDays": rec["lead_time_days"],
            "reliability": rec["reliability"],
        }
    report["headline"] = f"Replenish {sku} with {qty:,} units" + (f" from {rec['name']}" if rec else "")
    impact = []
    if rec:
        impact += [
            f"{rec['lead_time_days']}-day delivery"
            + (" — arrives before projected stockout" if rec["lead_time_days"] <= (inv.get("days_of_cover") or 0) else ""),
            f"{rec['reliability'] * 100:.0f}% supplier reliability",
        ]
    impact.insert(0, f"Stockout risk reduced from {risk} to low")
    report["impact"] = impact
    if rec:
        value = round(qty * rec["unit_price"], 2)
        if value > approval_threshold:
            report["approval"] = {
                "id": approval_id_for(state["run_id"]),
                "runId": state["run_id"],
                "sku": sku,
                "supplier": rec["name"],
                "supplierId": rec["supplier_id"],
                "quantity": qty,
                "unitPrice": rec["unit_price"],
                "value": value,
                "status": "pending",
                "reason": f"PO value ${value:,.0f} exceeds the ${approval_threshold:,.0f} approval threshold (Procurement Policy §4.2)",
                "expiresAt": (datetime.now(UTC) + timedelta(hours=approval_ttl_hours)).isoformat(),
            }
    return report


def fallback_summary(report: dict[str, Any], state: dict[str, Any]) -> str:
    """Deterministic narrative used when the synthesizer LLM is unavailable or its text fails validation."""
    inv = state.get("inventory_data") or {}
    if inv.get("sku") and report.get("headline", "").startswith("Replenish"):
        sup = report.get("supplier")
        tail = f" {sup['name']} can deliver in {sup['leadTimeDays']} days." if sup else ""
        return (
            f"{inv['sku']} has {inv['available']:,} units available against a 30-day forecast of {inv.get('forecast_30d', 0):,} units, "
            f"about {inv['days_of_cover']} days of cover versus a {inv['lead_time_days']}-day lead time.{tail}"
        )
    return report.get("headline", "")

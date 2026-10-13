"""Ratio analysis from financial statements and a simple DCF. Pure."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Statement:
    fiscal_year: int
    fiscal_period: str
    revenue: float
    gross_profit: float
    operating_income: float
    net_income: float
    ebitda: float
    interest_expense: float
    total_assets: float
    total_liabilities: float
    total_equity: float
    current_assets: float
    current_liabilities: float
    total_debt: float
    cash: float
    operating_cash_flow: float
    capex: float
    shares_outstanding: float

    @property
    def free_cash_flow(self) -> float:
        return self.operating_cash_flow - self.capex


def _div(a: float, b: float) -> float | None:
    return None if b == 0 else a / b


def ratios(current: Statement, previous: Statement | None = None) -> dict[str, float | None]:
    """Standard ratios. ``None`` where a denominator is zero (never invented)."""
    out: dict[str, float | None] = {
        "gross_margin": _div(current.gross_profit, current.revenue),
        "operating_margin": _div(current.operating_income, current.revenue),
        "net_margin": _div(current.net_income, current.revenue),
        "ebitda_margin": _div(current.ebitda, current.revenue),
        "roe": _div(current.net_income, current.total_equity),
        "roa": _div(current.net_income, current.total_assets),
        "current_ratio": _div(current.current_assets, current.current_liabilities),
        "debt_to_equity": _div(current.total_debt, current.total_equity),
        "net_debt_to_ebitda": _div(current.total_debt - current.cash, current.ebitda),
        "interest_coverage": _div(current.operating_income, current.interest_expense),
        "fcf_margin": _div(current.free_cash_flow, current.revenue),
        "revenue_growth": None,
        "operating_margin_change": None,
    }
    if previous is not None and previous.fiscal_period == current.fiscal_period:
        growth = _div(current.revenue - previous.revenue, previous.revenue)
        out["revenue_growth"] = growth
        prev_margin = _div(previous.operating_income, previous.revenue)
        if prev_margin is not None and out["operating_margin"] is not None:
            out["operating_margin_change"] = out["operating_margin"] - prev_margin
    return out


@dataclass(frozen=True)
class DcfResult:
    enterprise_value: float
    equity_value: float
    per_share: float | None
    pv_explicit: float
    pv_terminal: float
    terminal_share: float
    assumptions: dict[str, float]


def dcf(
    free_cash_flow: float,
    *,
    growth: float,
    years: int,
    discount_rate: float,
    terminal_growth: float,
    net_debt: float,
    shares: float | None = None,
) -> DcfResult:
    """Two-stage DCF: explicit growth for ``years`` then Gordon growth terminal value."""
    if not 0 < discount_rate < 0.5:
        raise ValueError("discount_rate must be between 0 and 0.5")
    if terminal_growth >= discount_rate:
        raise ValueError("terminal_growth must be below discount_rate")
    if not 1 <= years <= 20:
        raise ValueError("years must be between 1 and 20")
    if not -0.5 < growth < 1.0:
        raise ValueError("growth must be between -50% and 100%")
    pv_explicit = 0.0
    fcf = free_cash_flow
    for t in range(1, years + 1):
        fcf *= 1 + growth
        pv_explicit += fcf / (1 + discount_rate) ** t
    terminal = fcf * (1 + terminal_growth) / (discount_rate - terminal_growth)
    pv_terminal = terminal / (1 + discount_rate) ** years
    ev = pv_explicit + pv_terminal
    equity = ev - net_debt
    return DcfResult(
        enterprise_value=ev,
        equity_value=equity,
        per_share=equity / shares if shares else None,
        pv_explicit=pv_explicit,
        pv_terminal=pv_terminal,
        terminal_share=pv_terminal / ev if ev else 0.0,
        assumptions={
            "growth": growth,
            "years": years,
            "discount_rate": discount_rate,
            "terminal_growth": terminal_growth,
            "base_fcf": free_cash_flow,
        },
    )

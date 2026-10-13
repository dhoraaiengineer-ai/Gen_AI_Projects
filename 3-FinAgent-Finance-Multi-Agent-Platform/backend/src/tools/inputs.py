"""Validated input types shared by tools (bounded, format-checked, no extra fields)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
)


def _upper(value: object) -> object:
    """Normalise before the pattern check (``pf-a`` → ``PF-A``)."""
    return value.strip().upper() if isinstance(value, str) else value


_Norm = BeforeValidator(_upper)
Ticker = Annotated[str, _Norm, StringConstraints(pattern=r"^[A-Z][A-Z0-9.\-]{0,9}$")]
PortfolioId = Annotated[str, _Norm, StringConstraints(pattern=r"^PF-[A-Z0-9\-]{1,20}$")]
CustomerId = Annotated[str, _Norm, StringConstraints(pattern=r"^CU-\d{6}$")]
TransactionRef = Annotated[str, _Norm, StringConstraints(pattern=r"^TX-\d{6,9}$")]


def _confidence(value: float) -> float:
    if value not in (0.95, 0.99):
        raise ValueError("confidence must be 0.95 or 0.99")
    return value


Confidence = Annotated[float, AfterValidator(_confidence)]


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_max_length=500)


class NoInput(ToolInput):
    pass


class TickerInput(ToolInput):
    ticker: Ticker


class PortfolioInput(ToolInput):
    portfolio_id: PortfolioId = Field(description="Portfolio code, e.g. PF-A")


class PortfolioOrTickerInput(ToolInput):
    portfolio_id: PortfolioId | None = None
    ticker: Ticker | None = None
    window_days: int = Field(default=252, ge=30, le=500)


class HistoryInput(ToolInput):
    ticker: Ticker
    days: int = Field(default=60, ge=5, le=520)


class TickersInput(ToolInput):
    tickers: list[Ticker] = Field(default_factory=list, max_length=10)
    query: str = Field(default="", max_length=200)
    limit: int = Field(default=5, ge=1, le=10)


class VarInput(ToolInput):
    portfolio_id: PortfolioId
    confidence: Confidence = 0.95
    method: Literal["historical", "parametric"] = "historical"
    horizon_days: int = Field(default=1, ge=1, le=10)

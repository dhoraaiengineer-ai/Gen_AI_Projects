"""Dependencies handed to tool handlers (built by the container)."""

from __future__ import annotations

from dataclasses import dataclass

from src.core.ports import NewsProvider
from src.data.processing.analytics import PortfolioAnalytics
from src.data.repositories.market import MarketRepository
from src.data.repositories.ml import MlRepository
from src.data.repositories.payments import PaymentsRepository
from src.data.repositories.portfolio import PortfolioRepository
from src.db.session import Database
from src.ml.registry import ModelStore
from src.rag.service import KnowledgeService


@dataclass(frozen=True)
class ToolDeps:
    db: Database
    market: MarketRepository
    portfolios: PortfolioRepository
    payments: PaymentsRepository
    analytics: PortfolioAnalytics
    market_news: NewsProvider  # synthetic news about the (fictional) instruments
    web_news: NewsProvider  # Tavily when configured, else synthetic
    risk_free_rate: float = 0.03
    models: ModelStore | None = None  # None = ML tools answer model_unavailable
    ml_repo: MlRepository | None = None  # None = predictions are not persisted
    kb: KnowledgeService | None = None  # None = document tools answer provider_unavailable

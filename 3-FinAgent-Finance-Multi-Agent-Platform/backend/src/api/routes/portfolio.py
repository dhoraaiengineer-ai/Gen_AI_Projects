"""Portfolio, risk and identity routes (views)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from src.api.deps import get_container
from src.api.limits import limited
from src.container import Container
from src.presenters.portfolio import PortfolioPresenter, me_view
from src.schemas.views import MeView, PortfolioListItem, PortfolioView, RiskView
from src.security.auth import Principal, require_user

router = APIRouter(prefix="/api/v1", tags=["portfolio"])

Reader = Annotated[Principal, Depends(limited("dashboard:read", "read"))]
Deps = Annotated[Container, Depends(get_container)]
PortfolioCode = Annotated[str, Path(pattern=r"^(?i:PF-[A-Z0-9\-]{1,20})$")]


@router.get("/me", response_model=MeView, response_model_by_alias=True)
async def me(principal: Annotated[Principal, Depends(require_user)]) -> MeView:
    return me_view(principal)


@router.get("/portfolios", response_model=list[PortfolioListItem], response_model_by_alias=True)
async def portfolios(principal: Reader, container: Deps) -> list[PortfolioListItem]:
    return await PortfolioPresenter(container).list()


@router.get("/portfolio/{portfolio_id}", response_model=PortfolioView, response_model_by_alias=True)
async def portfolio(
    portfolio_id: PortfolioCode, principal: Reader, container: Deps
) -> PortfolioView:
    return await PortfolioPresenter(container).detail(portfolio_id)


@router.get("/risk/{portfolio_id}", response_model=RiskView, response_model_by_alias=True)
async def risk(portfolio_id: PortfolioCode, principal: Reader, container: Deps) -> RiskView:
    return await PortfolioPresenter(container).risk(portfolio_id)

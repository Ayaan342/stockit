from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.stock import Stock
from app.schemas.stock import StockHistoryPoint, StockResponse
from app.services.market_data import MarketDataError, MarketDataService

router = APIRouter(prefix="/stocks", tags=["stocks"])


def get_market_service(request: Request) -> MarketDataService:
    return request.app.state.market_service


def provider_error(exc: MarketDataError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.public_detail)


@router.get("", response_model=list[StockResponse])
def list_stocks(limit: int = Query(default=50, ge=1, le=100), db: Session = Depends(get_db)) -> list[Stock]:
    return list(db.scalars(select(Stock).order_by(Stock.symbol).limit(limit)))


@router.get("/search", response_model=list[StockResponse])
async def search_stocks(
    q: str = Query(min_length=1, max_length=100),
    db: Session = Depends(get_db),
    market: MarketDataService = Depends(get_market_service),
) -> list[Stock]:
    try:
        return await market.search(db, q)
    except MarketDataError as exc:
        raise provider_error(exc) from exc


@router.get("/{symbol}", response_model=StockResponse)
async def stock_details(symbol: str, db: Session = Depends(get_db), market: MarketDataService = Depends(get_market_service)) -> Stock:
    try:
        return await market.get_stock(db, symbol)
    except MarketDataError as exc:
        raise provider_error(exc) from exc


@router.get("/{symbol}/history", response_model=list[StockHistoryPoint])
async def stock_history(symbol: str, market: MarketDataService = Depends(get_market_service)) -> list[StockHistoryPoint]:
    try:
        return await market.history(symbol)
    except MarketDataError as exc:
        raise provider_error(exc) from exc

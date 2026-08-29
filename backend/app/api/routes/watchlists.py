from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db
from app.api.routes.stocks import get_market_service, provider_error
from app.models.user import User
from app.models.watchlist import Watchlist, WatchlistStock
from app.schemas.stock import StockResponse
from app.schemas.watchlist import WatchlistCreate, WatchlistResponse
from app.services.market_data import MarketDataError, MarketDataService, normalize_symbol

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


def serialize(watchlist: Watchlist) -> WatchlistResponse:
    return WatchlistResponse(
        id=watchlist.id,
        name=watchlist.name,
        created_at=watchlist.created_at,
        stocks=[StockResponse.model_validate(entry.stock) for entry in watchlist.stocks],
    )


def owned_watchlist(db: Session, user_id: int, watchlist_id: int) -> Watchlist:
    watchlist = db.scalar(
        select(Watchlist).options(selectinload(Watchlist.stocks).selectinload(WatchlistStock.stock)).where(
            Watchlist.id == watchlist_id, Watchlist.user_id == user_id
        )
    )
    if watchlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found")
    return watchlist


@router.get("", response_model=list[WatchlistResponse])
def list_watchlists(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[WatchlistResponse]:
    watchlists = db.scalars(
        select(Watchlist).options(selectinload(Watchlist.stocks).selectinload(WatchlistStock.stock)).where(
            Watchlist.user_id == current_user.id
        ).order_by(Watchlist.created_at)
    )
    return [serialize(watchlist) for watchlist in watchlists]


@router.post("", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
def create_watchlist(payload: WatchlistCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> WatchlistResponse:
    watchlist = Watchlist(user_id=current_user.id, name=payload.name.strip())
    try:
        db.add(watchlist)
        db.commit()
        db.refresh(watchlist)
        return serialize(watchlist)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A watchlist with this name already exists") from exc


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist(watchlist_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    db.delete(owned_watchlist(db, current_user.id, watchlist_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{watchlist_id}/stocks/{symbol}", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
async def add_stock(
    watchlist_id: int, symbol: str, exchange: str | None = Query(default=None, min_length=1, max_length=64), current_user: User = Depends(get_current_user), db: Session = Depends(get_db), market: MarketDataService = Depends(get_market_service)
) -> WatchlistResponse:
    watchlist = owned_watchlist(db, current_user.id, watchlist_id)
    try:
        stock = await market.get_stock(db, symbol, exchange=exchange)
    except MarketDataError as exc:
        raise provider_error(exc) from exc
    if any(entry.stock_id == stock.id for entry in watchlist.stocks):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stock is already in this watchlist")
    try:
        db.add(WatchlistStock(watchlist_id=watchlist.id, stock_id=stock.id))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stock is already in this watchlist") from exc
    return serialize(owned_watchlist(db, current_user.id, watchlist_id))


@router.delete("/{watchlist_id}/stocks/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
def remove_stock(watchlist_id: int, symbol: str, exchange: str | None = Query(default=None, min_length=1, max_length=64), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    watchlist = owned_watchlist(db, current_user.id, watchlist_id)
    entry = next((entry for entry in watchlist.stocks if entry.stock.symbol == normalize_symbol(symbol) and (exchange is None or entry.stock.exchange == exchange.upper())), None)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock is not in this watchlist")
    db.delete(entry)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

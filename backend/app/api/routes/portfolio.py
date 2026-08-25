from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, get_db
from app.api.routes.stocks import get_market_service, provider_error
from app.models.portfolio import Holding, Portfolio, Transaction
from app.models.user import User
from app.schemas.portfolio import (
    HoldingResponse,
    PortfolioPerformancePoint,
    PortfolioResponse,
    TradeRequest,
    TransactionResponse,
)
from app.services.market_data import MarketDataError, MarketDataService, normalize_symbol
from app.services.portfolio import holding_response, money, realized_profit_loss

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def get_portfolio(db: Session, user_id: int, *, lock: bool = False) -> Portfolio:
    statement = select(Portfolio).where(Portfolio.user_id == user_id)
    if lock:
        statement = statement.with_for_update()
    portfolio = db.scalar(statement)
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    return portfolio


async def valued_holdings(db: Session, portfolio: Portfolio, market: MarketDataService) -> list[HoldingResponse]:
    holdings = db.scalars(
        select(Holding).options(joinedload(Holding.stock)).where(Holding.portfolio_id == portfolio.id).order_by(Holding.id)
    )
    responses: list[HoldingResponse] = []
    for holding in holdings:
        try:
            stock = await market.get_stock(db, holding.stock.symbol, require_price=True)
        except MarketDataError as exc:
            raise provider_error(exc) from exc
        responses.append(holding_response(holding, stock.last_price))
    return responses


def transaction_response(transaction: Transaction) -> TransactionResponse:
    return TransactionResponse(
        id=transaction.id,
        symbol=transaction.stock.symbol,
        transaction_type=transaction.transaction_type,
        quantity=transaction.quantity,
        price=transaction.price,
        total_amount=transaction.total_amount,
        created_at=transaction.created_at,
    )


@router.get("", response_model=PortfolioResponse)
async def portfolio_summary(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db), market: MarketDataService = Depends(get_market_service)
) -> PortfolioResponse:
    portfolio = get_portfolio(db, current_user.id)
    holdings = await valued_holdings(db, portfolio, market)
    transactions = list(
        db.scalars(
            select(Transaction).where(Transaction.portfolio_id == portfolio.id).order_by(Transaction.created_at, Transaction.id)
        )
    )
    total_invested = money(sum((item.invested_value for item in holdings), Decimal("0")))
    current_holdings_value = money(sum((item.current_value for item in holdings), Decimal("0")))
    total_value = money(current_user.virtual_cash_balance + current_holdings_value)
    unrealized = money(sum((item.profit_loss for item in holdings), Decimal("0")))
    realized = realized_profit_loss(transactions)
    profit_loss = money(realized + unrealized)
    percentage = None if total_invested == 0 else (profit_loss / total_invested * Decimal("100")).quantize(Decimal("0.01"))
    return PortfolioResponse(
        portfolio_id=portfolio.id,
        cash_balance=current_user.virtual_cash_balance,
        total_invested=total_invested,
        current_holdings_value=current_holdings_value,
        realized_profit_loss=realized,
        unrealized_profit_loss=unrealized,
        total_portfolio_value=total_value,
        total_profit_loss=profit_loss,
        profit_loss_percentage=percentage,
        day_change=None,
    )


@router.get("/holdings", response_model=list[HoldingResponse])
async def list_holdings(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db), market: MarketDataService = Depends(get_market_service)
) -> list[HoldingResponse]:
    return await valued_holdings(db, get_portfolio(db, current_user.id), market)


@router.get("/transactions", response_model=list[TransactionResponse])
def list_transactions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[TransactionResponse]:
    transactions = db.scalars(
        select(Transaction).options(joinedload(Transaction.stock)).where(Transaction.user_id == current_user.id).order_by(Transaction.created_at.desc(), Transaction.id.desc())
    )
    return [transaction_response(transaction) for transaction in transactions]


@router.get("/performance", response_model=list[PortfolioPerformancePoint])
async def performance(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db), market: MarketDataService = Depends(get_market_service)
) -> list[PortfolioPerformancePoint]:
    """Returns the current valuation until historical portfolio snapshots are introduced."""
    summary = await portfolio_summary(current_user, db, market)
    return [PortfolioPerformancePoint(timestamp=datetime.now(timezone.utc), portfolio_value=summary.total_portfolio_value)]


@router.post("/buy", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def buy(
    payload: TradeRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db), market: MarketDataService = Depends(get_market_service)
) -> TransactionResponse:
    try:
        stock = await market.get_stock(db, normalize_symbol(payload.symbol), require_price=True)
    except MarketDataError as exc:
        raise provider_error(exc) from exc
    try:
        # Lock the user and portfolio rows so simultaneous orders cannot overspend cash.
        user = db.scalar(select(User).where(User.id == current_user.id).with_for_update())
        portfolio = get_portfolio(db, current_user.id, lock=True)
        holding = db.scalar(
            select(Holding).where(Holding.portfolio_id == portfolio.id, Holding.stock_id == stock.id).with_for_update()
        )
        total = money(payload.quantity * stock.last_price)
        if user is None or user.virtual_cash_balance < total:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient virtual cash")
        user.virtual_cash_balance = money(user.virtual_cash_balance - total)
        if holding is None:
            holding = Holding(portfolio_id=portfolio.id, stock_id=stock.id, quantity=payload.quantity, average_buy_price=stock.last_price)
            db.add(holding)
        else:
            combined_quantity = holding.quantity + payload.quantity
            holding.average_buy_price = (holding.quantity * holding.average_buy_price + payload.quantity * stock.last_price) / combined_quantity
            holding.quantity = combined_quantity
        transaction = Transaction(
            user_id=user.id, portfolio_id=portfolio.id, stock_id=stock.id, transaction_type="BUY",
            quantity=payload.quantity, price=stock.last_price, total_amount=total,
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        db.refresh(transaction, attribute_names=["stock"])
        return transaction_response(transaction)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to execute buy order")


@router.post("/sell", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def sell(
    payload: TradeRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db), market: MarketDataService = Depends(get_market_service)
) -> TransactionResponse:
    try:
        stock = await market.get_stock(db, normalize_symbol(payload.symbol), require_price=True)
    except MarketDataError as exc:
        raise provider_error(exc) from exc
    try:
        user = db.scalar(select(User).where(User.id == current_user.id).with_for_update())
        portfolio = get_portfolio(db, current_user.id, lock=True)
        holding = db.scalar(
            select(Holding).where(Holding.portfolio_id == portfolio.id, Holding.stock_id == stock.id).with_for_update()
        )
        if user is None or holding is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No holding exists for this stock")
        if payload.quantity > holding.quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sell quantity exceeds owned shares")
        total = money(payload.quantity * stock.last_price)
        user.virtual_cash_balance = money(user.virtual_cash_balance + total)
        holding.quantity -= payload.quantity
        if holding.quantity == 0:
            db.delete(holding)
        transaction = Transaction(
            user_id=user.id, portfolio_id=portfolio.id, stock_id=stock.id, transaction_type="SELL",
            quantity=payload.quantity, price=stock.last_price, total_amount=total,
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        db.refresh(transaction, attribute_names=["stock"])
        return transaction_response(transaction)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to execute sell order")

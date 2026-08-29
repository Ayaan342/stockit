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
    PortfolioCurrencyGroup,
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
            stock = await market.get_stock(db, holding.stock.symbol, exchange=holding.stock.exchange, require_price=True)
            responses.append(holding_response(holding, stock.last_price))
        except MarketDataError:
            # A position is recorded accounting data. Market valuation is
            # optional enrichment and must never hide a valid holding.
            responses.append(holding_response(holding, None))
    currency_totals: dict[str, Decimal] = {}
    for item in responses:
        if item.current_value is not None:
            currency_totals[item.currency] = currency_totals.get(item.currency, Decimal("0")) + item.current_value
    incomplete_currencies = {
        item.currency for item in responses if item.current_value is None
    }
    for item in responses:
        total = currency_totals.get(item.currency, Decimal("0"))
        item.allocation_percentage = None if item.currency in incomplete_currencies or total == 0 or item.current_value is None else (item.current_value / total * Decimal("100")).quantize(Decimal("0.01"))
    return responses


def transaction_response(transaction: Transaction) -> TransactionResponse:
    return TransactionResponse(
        id=transaction.id,
        symbol=transaction.stock.symbol,
        exchange=transaction.stock.exchange,
        currency=transaction.stock.currency,
        transaction_type=transaction.transaction_type,
        quantity=transaction.quantity,
        price=transaction.price,
        total_amount=transaction.total_amount,
        fees=transaction.fees,
        notes=transaction.notes,
        executed_at=transaction.executed_at,
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
    currencies = {item.currency for item in holdings} | {transaction.stock.currency for transaction in transactions}
    groups: list[PortfolioCurrencyGroup] = []
    for currency in sorted(currencies):
        group_holdings = [item for item in holdings if item.currency == currency]
        group_transactions = [item for item in transactions if item.stock.currency == currency]
        invested = money(sum((item.invested_value for item in group_holdings), Decimal("0")))
        realized = realized_profit_loss(group_transactions)
        valuation_complete = all(
            item.current_value is not None and item.profit_loss is not None
            for item in group_holdings
        )
        value = money(sum((item.current_value for item in group_holdings), Decimal("0"))) if valuation_complete else None
        unrealized = money(sum((item.profit_loss for item in group_holdings), Decimal("0"))) if valuation_complete else None
        total_profit_loss = money(realized + unrealized) if unrealized is not None else None
        percentage = None if invested == 0 or total_profit_loss is None else (total_profit_loss / invested * Decimal("100")).quantize(Decimal("0.01"))
        groups.append(PortfolioCurrencyGroup(
            currency=currency,
            market_group="INDIA" if currency == "INR" else "US" if currency == "USD" else currency,
            total_invested=invested, current_holdings_value=value, realized_profit_loss=realized,
            unrealized_profit_loss=unrealized, total_portfolio_value=value,
            total_profit_loss=total_profit_loss, profit_loss_percentage=percentage,
            number_of_assets=len(group_holdings),
        ))
    response = PortfolioResponse(portfolio_id=portfolio.id, groups=groups, day_change=None)
    if not groups:
        response.total_invested = Decimal("0.00")
        response.current_holdings_value = Decimal("0.00")
        response.realized_profit_loss = Decimal("0.00")
        response.unrealized_profit_loss = Decimal("0.00")
        response.total_portfolio_value = Decimal("0.00")
        response.total_profit_loss = Decimal("0.00")
    if len(groups) == 1:
        group = groups[0]
        response.total_invested = group.total_invested
        response.current_holdings_value = group.current_holdings_value
        response.realized_profit_loss = group.realized_profit_loss
        response.unrealized_profit_loss = group.unrealized_profit_loss
        response.total_portfolio_value = group.total_portfolio_value
        response.total_profit_loss = group.total_profit_loss
        response.profit_loss_percentage = group.profit_loss_percentage
    return response


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
    # Performance snapshots are not yet stored. Do not merge currency values.
    return []


@router.post("/buy", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def buy(
    payload: TradeRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db), market: MarketDataService = Depends(get_market_service)
) -> TransactionResponse:
    try:
        stock = await market.resolve_stock(db, payload.symbol, exchange=payload.exchange)
    except MarketDataError as exc:
        raise provider_error(exc) from exc
    try:
        portfolio = get_portfolio(db, current_user.id, lock=True)
        holding = db.scalar(
            select(Holding).where(Holding.portfolio_id == portfolio.id, Holding.stock_id == stock.id).with_for_update()
        )
        total = money(payload.quantity * payload.price + payload.fees)
        if holding is None:
            holding = Holding(portfolio_id=portfolio.id, stock_id=stock.id, quantity=payload.quantity, average_buy_price=total / payload.quantity)
            db.add(holding)
        else:
            combined_quantity = holding.quantity + payload.quantity
            holding.average_buy_price = (holding.quantity * holding.average_buy_price + total) / combined_quantity
            holding.quantity = combined_quantity
        transaction = Transaction(
            user_id=current_user.id, portfolio_id=portfolio.id, stock_id=stock.id, transaction_type="BUY",
            quantity=payload.quantity, price=payload.price, total_amount=total, fees=payload.fees, notes=payload.notes,
            executed_at=payload.executed_at or datetime.now(timezone.utc),
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
        stock = await market.resolve_stock(db, payload.symbol, exchange=payload.exchange)
    except MarketDataError as exc:
        raise provider_error(exc) from exc
    try:
        portfolio = get_portfolio(db, current_user.id, lock=True)
        holding = db.scalar(
            select(Holding).where(Holding.portfolio_id == portfolio.id, Holding.stock_id == stock.id).with_for_update()
        )
        if holding is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No holding exists for this stock")
        if payload.quantity > holding.quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Insufficient quantity. You currently own {holding.quantity} shares.")
        total = money(payload.quantity * payload.price - payload.fees)
        if total < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fees cannot exceed sale proceeds")
        holding.quantity -= payload.quantity
        if holding.quantity == 0:
            db.delete(holding)
        transaction = Transaction(
            user_id=current_user.id, portfolio_id=portfolio.id, stock_id=stock.id, transaction_type="SELL",
            quantity=payload.quantity, price=payload.price, total_amount=total, fees=payload.fees, notes=payload.notes,
            executed_at=payload.executed_at or datetime.now(timezone.utc),
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

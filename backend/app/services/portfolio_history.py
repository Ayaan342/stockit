"""Transaction-ledger portfolio history calculations."""

import asyncio
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.portfolio import Portfolio, Transaction
from app.schemas.portfolio import PortfolioHistoryPoint, PortfolioHistoryResponse
from app.schemas.stock import StockHistoryPoint
from app.services.market_data import MarketDataError, MarketDataService

_PERIOD_DAYS = {"30d": 30, "1y": 365}


def _transaction_date(value: datetime) -> date:
    normalized = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return normalized.date()


async def portfolio_history(
    db: Session,
    portfolio: Portfolio,
    market: MarketDataService,
    *,
    currency: str,
    period: str,
    today: date | None = None,
) -> PortfolioHistoryResponse:
    days = _PERIOD_DAYS[period]
    end = today or datetime.now(timezone.utc).date()
    start = end - timedelta(days=days - 1)
    transactions = list(db.scalars(
        select(Transaction).options(joinedload(Transaction.stock)).where(
            Transaction.portfolio_id == portfolio.id,
            Transaction.stock.has(currency=currency),
        ).order_by(Transaction.executed_at, Transaction.id)
    ))
    stocks = {transaction.stock.id: transaction.stock for transaction in transactions}
    # Request a short lookback so weekends/holidays can carry forward the last
    # real close without making a per-day provider request.
    history_days = 45 if period == "30d" else 400
    results = await asyncio.gather(
        *(market.history_for_days(stock.symbol, exchange=stock.exchange, days=history_days) for stock in stocks.values()),
        return_exceptions=True,
    )
    prices: dict[int, dict[date, Decimal]] = {}
    complete = True
    for stock, result in zip(stocks.values(), results, strict=True):
        if isinstance(result, Exception):
            complete = False
            prices[stock.id] = {}
            continue
        series: dict[date, Decimal] = {}
        for point in result:
            timestamp = point.timestamp.replace(tzinfo=timezone.utc) if point.timestamp.tzinfo is None else point.timestamp.astimezone(timezone.utc)
            series[timestamp.date()] = point.close
        prices[stock.id] = series

    transactions_by_date: dict[date, list[Transaction]] = defaultdict(list)
    for transaction in transactions:
        transactions_by_date[_transaction_date(transaction.executed_at)].append(transaction)
    quantities: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    last_prices: dict[int, Decimal] = {}
    points: list[PortfolioHistoryPoint] = []
    # Replay all earlier ledger events once; do not loop through potentially
    # years of calendar days before the requested chart range.
    for transaction in transactions:
        if _transaction_date(transaction.executed_at) < start:
            quantities[transaction.stock_id] += transaction.quantity if transaction.transaction_type == "BUY" else -transaction.quantity

    for offset in range(days):
        day = start + timedelta(days=offset)
        for transaction in transactions_by_date.get(day, []):
            quantities[transaction.stock_id] += transaction.quantity if transaction.transaction_type == "BUY" else -transaction.quantity
        total = Decimal("0")
        day_complete = True
        for stock_id, quantity in quantities.items():
            if quantity <= 0:
                continue
            close = prices.get(stock_id, {}).get(day)
            if close is not None:
                last_prices[stock_id] = close
            close = last_prices.get(stock_id)
            if close is None:
                day_complete = False
                continue
            total += quantity * close
        points.append(PortfolioHistoryPoint(date=day, value=total.quantize(Decimal("0.01")) if day_complete else None))
        complete = complete and day_complete
    return PortfolioHistoryResponse(currency=currency, period=period, complete=complete, points=points)

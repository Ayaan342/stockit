from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class TradeRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)


class HoldingResponse(BaseModel):
    symbol: str
    name: str
    quantity: Decimal
    average_buy_price: Decimal
    current_market_price: Decimal
    invested_value: Decimal
    current_value: Decimal
    profit_loss: Decimal
    profit_loss_percentage: Decimal | None


class TransactionResponse(BaseModel):
    id: int
    symbol: str
    transaction_type: str
    quantity: Decimal
    price: Decimal
    total_amount: Decimal
    created_at: datetime


class PortfolioResponse(BaseModel):
    portfolio_id: int
    cash_balance: Decimal
    total_invested: Decimal
    current_holdings_value: Decimal
    realized_profit_loss: Decimal
    unrealized_profit_loss: Decimal
    total_portfolio_value: Decimal
    total_profit_loss: Decimal
    profit_loss_percentage: Decimal | None
    day_change: Decimal | None = None


class PortfolioPerformancePoint(BaseModel):
    timestamp: datetime
    portfolio_value: Decimal

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class TradeRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    exchange: str | None = Field(default=None, min_length=1, max_length=64)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    price: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    fees: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    executed_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)


class HoldingResponse(BaseModel):
    symbol: str
    name: str
    exchange: str
    currency: str
    quantity: Decimal
    average_buy_price: Decimal
    current_market_price: Decimal | None
    invested_value: Decimal
    current_value: Decimal | None
    profit_loss: Decimal | None
    profit_loss_percentage: Decimal | None
    allocation_percentage: Decimal | None


class TransactionResponse(BaseModel):
    id: int
    symbol: str
    exchange: str
    currency: str
    transaction_type: str
    quantity: Decimal
    price: Decimal
    total_amount: Decimal
    fees: Decimal
    notes: str | None
    executed_at: datetime
    created_at: datetime


class PortfolioCurrencyGroup(BaseModel):
    currency: str
    market_group: str
    total_invested: Decimal
    current_holdings_value: Decimal | None
    realized_profit_loss: Decimal
    unrealized_profit_loss: Decimal | None
    total_portfolio_value: Decimal | None
    total_profit_loss: Decimal | None
    profit_loss_percentage: Decimal | None
    number_of_assets: int


class PortfolioResponse(BaseModel):
    portfolio_id: int
    groups: list[PortfolioCurrencyGroup]
    # Legacy top-level values are available only for a single-currency
    # portfolio. They are deliberately absent for mixed currencies, where a
    # combined number would be invalid without FX conversion.
    total_invested: Decimal | None = None
    current_holdings_value: Decimal | None = None
    realized_profit_loss: Decimal | None = None
    unrealized_profit_loss: Decimal | None = None
    total_portfolio_value: Decimal | None = None
    total_profit_loss: Decimal | None = None
    profit_loss_percentage: Decimal | None = None
    day_change: Decimal | None = None


class PortfolioPerformancePoint(BaseModel):
    timestamp: datetime
    portfolio_value: Decimal

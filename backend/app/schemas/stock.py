from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class StockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    name: str
    exchange: str | None
    currency: str
    last_price: Decimal | None
    last_price_updated_at: datetime | None


class StockHistoryPoint(BaseModel):
    timestamp: datetime
    close: Decimal = Field(ge=0)

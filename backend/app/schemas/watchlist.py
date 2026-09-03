from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.stock import StockResponse


class WatchlistCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)


class WatchlistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    stocks: list[StockResponse] = Field(default_factory=list)

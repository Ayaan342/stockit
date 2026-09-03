from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Stock(Base):
    __tablename__ = "stocks"
    __table_args__ = (UniqueConstraint("symbol", "exchange", name="uq_stocks_symbol_exchange"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # A ticker is only meaningful with its selected listing (for example TCS
    # on NSE is not the same instrument as TCS on BSE).
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    exchange: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    last_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    last_price_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    holdings: Mapped[list["Holding"]] = relationship(back_populates="stock")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="stock")
    watchlist_entries: Mapped[list["WatchlistStock"]] = relationship(back_populates="stock")

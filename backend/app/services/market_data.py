"""Market-data provider boundary. Provider responses are never invented or synthesized."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.stock import Stock
from app.schemas.stock import StockHistoryPoint


class MarketDataError(Exception):
    def __init__(self, public_detail: str = "Market data is currently unavailable", status_code: int = 503) -> None:
        super().__init__(public_detail)
        self.public_detail = public_detail
        self.status_code = status_code


class MarketDataProvider(ABC):
    @abstractmethod
    async def search(self, query: str) -> list[dict]: ...

    @abstractmethod
    async def quote(self, symbol: str) -> Decimal: ...

    @abstractmethod
    async def details(self, symbol: str) -> dict: ...

    @abstractmethod
    async def history(self, symbol: str) -> list[StockHistoryPoint]: ...


class TwelveDataProvider(MarketDataProvider):
    """Twelve Data REST adapter, isolated from StockIt's API and trade logic."""

    SEARCH_RESULT_LIMIT = 20
    _US_PRIMARY_EXCHANGES = frozenset({"NASDAQ", "NYSE", "NYSE ARCA", "AMEX"})
    _STRUCTURED_TYPE_MARKERS = ("depositary", "structured", "note", "warrant", "bond", "fund")

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._base_url = settings.market_data_base_url.rstrip("/")
        self._transport = transport
        self._pending_quotes: dict[str, dict] = {}

    def _headers(self) -> dict[str, str]:
        if not settings.market_data_api_key:
            raise MarketDataError("Market data is not configured")
        return {"Authorization": f"apikey {settings.market_data_api_key}"}

    async def _get(self, path: str, params: dict[str, str]) -> dict:
        try:
            async with httpx.AsyncClient(timeout=10.0, transport=self._transport) as client:
                response = await client.get(f"{self._base_url}{path}", params=params, headers=self._headers())
        except httpx.TimeoutException as exc:
            raise MarketDataError("Market data provider timed out") from exc
        except httpx.HTTPError as exc:
            raise MarketDataError("Market data provider request failed") from exc
        if response.status_code == 429:
            raise MarketDataError("Market data rate limit reached", status_code=429)
        if response.status_code in {401, 403} or response.status_code >= 500:
            raise MarketDataError("Market data provider is currently unavailable")
        if response.status_code >= 400:
            raise MarketDataError("Stock data was not found", status_code=404)
        try:
            payload = response.json()
        except ValueError as exc:
            raise MarketDataError("Market data provider returned an invalid response") from exc
        if not isinstance(payload, dict):
            raise MarketDataError("Market data provider returned an invalid response")
        if payload.get("status") == "error" or payload.get("code") in {401, 403, 429}:
            code = payload.get("code")
            if code == 429:
                raise MarketDataError("Market data rate limit reached", status_code=429)
            if code in {401, 403}:
                raise MarketDataError("Market data provider is currently unavailable")
            raise MarketDataError("Stock data was not found", status_code=404)
        return payload

    async def search(self, query: str) -> list[dict]:
        payload = await self._get("/symbol_search", {"symbol": query})
        data = payload.get("data")
        if not isinstance(data, list):
            raise MarketDataError("Market data provider returned an invalid response")
        normalized_query = normalize_symbol(query)
        seen: set[tuple[str, str, str]] = set()
        candidates: list[tuple[dict, dict, int]] = []
        for source_index, item in enumerate(data):
            if not isinstance(item, dict) or not item.get("symbol"):
                continue
            symbol = normalize_symbol(str(item["symbol"]))
            exchange = str(item.get("exchange") or "").strip().upper()
            currency = str(item.get("currency") or "").strip().upper()
            identity = (symbol, exchange, currency)
            if identity in seen:
                continue
            seen.add(identity)
            candidates.append((
                {
                    "symbol": symbol,
                    "name": item.get("instrument_name") or item.get("name") or item["symbol"],
                    "exchange": exchange or None,
                    "currency": currency or "USD",
                },
                item,
                source_index,
            ))

        def rank(candidate: tuple[dict, dict, int]) -> tuple[int, int, int, int]:
            result, metadata, source_index = candidate
            symbol = result["symbol"]
            instrument_type = str(metadata.get("type") or metadata.get("instrument_type") or "").lower()
            exact_match = 0 if symbol == normalized_query else 1
            if any(marker in instrument_type for marker in self._STRUCTURED_TYPE_MARKERS):
                type_rank = 2
            elif "common stock" in instrument_type or instrument_type in {"stock", "equity", "share"}:
                type_rank = 0
            else:
                type_rank = 1
            exchange = str(result.get("exchange") or "").upper()
            country = str(metadata.get("country") or "").lower()
            currency = str(result.get("currency") or "").upper()
            primary_us_listing = (
                ":" not in normalized_query
                and exchange in self._US_PRIMARY_EXCHANGES
                and currency == "USD"
                and country in {"united states", "us", "usa"}
                and type_rank == 0
            )
            return (exact_match, type_rank, 0 if primary_us_listing else 1, source_index)

        candidates.sort(key=rank)
        return [result for result, _, _ in candidates[:self.SEARCH_RESULT_LIMIT]]

    async def quote(self, symbol: str) -> Decimal:
        payload = self._pending_quotes.pop(symbol, None) or await self._get("/quote", {"symbol": symbol})
        try:
            raw_price = payload.get("close") if payload.get("close") is not None else payload.get("price")
            price = Decimal(str(raw_price))
        except (InvalidOperation, TypeError) as exc:
            raise MarketDataError("Market data provider returned an invalid quote") from exc
        if price <= 0:
            raise MarketDataError("Market data provider returned no current quote")
        return price

    async def details(self, symbol: str) -> dict:
        payload = await self._get("/quote", {"symbol": symbol})
        if not payload.get("symbol"):
            raise MarketDataError("Stock data was not found", status_code=404)
        self._pending_quotes[symbol] = payload
        return {"symbol": str(payload["symbol"]).upper(), "name": payload.get("name") or payload["symbol"], "exchange": payload.get("exchange"), "currency": payload.get("currency")}

    async def history(self, symbol: str) -> list[StockHistoryPoint]:
        payload = await self._get("/time_series", {"symbol": symbol, "interval": "1day", "outputsize": "30", "order": "asc", "timezone": "UTC"})
        values = payload.get("values")
        if not isinstance(values, list) or not values:
            raise MarketDataError("Stock price history was not found", status_code=404)
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        try:
            exchange_timezone = ZoneInfo(meta.get("exchange_timezone") or "UTC")
        except ZoneInfoNotFoundError:
            exchange_timezone = timezone.utc
        try:
            points = []
            for value in values:
                timestamp = datetime.fromisoformat(str(value["datetime"]).replace("Z", "+00:00"))
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=exchange_timezone)
                points.append(StockHistoryPoint(timestamp=timestamp.astimezone(timezone.utc), close=Decimal(str(value["close"]))))
            return points
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise MarketDataError("Market data provider returned an invalid history response") from exc


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def provider_symbol(symbol: str, exchange: str | None = None) -> str:
    """Return the selected Twelve Data listing identifier without guessing an exchange."""
    normalized_symbol = normalize_symbol(symbol)
    if ":" in normalized_symbol or not exchange:
        return normalized_symbol
    return f"{normalized_symbol}:{exchange.strip().upper()}"


class MarketDataService:
    def __init__(self, provider: MarketDataProvider) -> None:
        self.provider = provider

    async def search(self, db: Session, query: str) -> list[Stock]:
        results = await self.provider.search(query)
        # The cache table intentionally has one row per symbol, while provider
        # search can return several exchange/currency listings for that symbol.
        # Return distinct transient result objects; only cache the best-ranked
        # listing for each symbol so one ORM row cannot overwrite every result.
        stocks: list[Stock] = []
        seen_listings: set[tuple[str, str, str]] = set()
        cached_symbols: set[str] = set()
        for result in results:
            symbol = normalize_symbol(result["symbol"])
            exchange = str(result.get("exchange") or "").strip().upper()
            currency = str(result.get("currency") or "").strip().upper()
            listing_identity = (symbol, exchange, currency)
            if listing_identity in seen_listings:
                continue
            seen_listings.add(listing_identity)
            if symbol not in cached_symbols:
                self._upsert_stock(db, result)
                cached_symbols.add(symbol)
            stocks.append(
                Stock(
                    symbol=symbol,
                    name=result.get("name") or symbol,
                    exchange=exchange or None,
                    currency=currency or "USD",
                )
            )
        db.commit()
        return stocks

    def _upsert_stock(self, db: Session, data: dict) -> Stock:
        symbol = normalize_symbol(data["symbol"])
        stock = db.scalar(select(Stock).where(Stock.symbol == symbol))
        if stock is None:
            # The unique symbol constraint remains the source of truth. A
            # savepoint turns a concurrent insert into a safe fetch of its row.
            try:
                with db.begin_nested():
                    stock = Stock(
                        symbol=symbol,
                        name=data.get("name") or symbol,
                        exchange=data.get("exchange"),
                        currency=data.get("currency") or "USD",
                    )
                    db.add(stock)
                    db.flush()
            except IntegrityError:
                stock = db.scalar(select(Stock).where(Stock.symbol == symbol))
                if stock is None:
                    raise
        else:
            stock.name = data.get("name") or stock.name
            stock.exchange = data.get("exchange") or stock.exchange
            stock.currency = data.get("currency") or stock.currency
        return stock

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        """Normalize DB values without re-labelling non-UTC aware timestamps."""
        if value.tzinfo is None:
            # SQLite test databases return naive values; PostgreSQL returns aware
            # values for TIMESTAMP WITH TIME ZONE columns.
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    async def get_stock(self, db: Session, symbol: str, *, exchange: str | None = None, require_price: bool = False) -> Stock:
        symbol = normalize_symbol(symbol)
        selected_provider_symbol = provider_symbol(symbol, exchange)
        stock = db.scalar(select(Stock).where(Stock.symbol == symbol))
        stale = stock is None or stock.last_price_updated_at is None or (
            datetime.now(timezone.utc) - self._as_utc(stock.last_price_updated_at)
        ).total_seconds() > settings.market_cache_seconds
        # A cached row represents the bare stock symbol. Refresh when the user
        # explicitly selected another exchange so Twelve Data resolves that
        # exact listing rather than an arbitrary symbol match.
        if exchange:
            # The cache is keyed by bare symbol, so it cannot prove that its
            # value belongs to a user-selected listing. Always resolve an
            # explicit exchange with Twelve Data before returning details.
            stale = True
        if stale:
            details = await self.provider.details(selected_provider_symbol)
            stock = self._upsert_stock(db, details)
            try:
                stock.last_price = await self.provider.quote(selected_provider_symbol)
                stock.last_price_updated_at = datetime.now(timezone.utc)
            except MarketDataError:
                if require_price or stock.last_price is None:
                    raise
            db.commit()
            db.refresh(stock)
        if require_price and (stock.last_price is None or stock.last_price <= 0):
            raise MarketDataError("No current market price is available")
        return stock

    async def history(self, symbol: str, *, exchange: str | None = None) -> list[StockHistoryPoint]:
        return await self.provider.history(provider_symbol(symbol, exchange))

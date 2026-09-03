"""Market-data provider boundary. Provider responses are never invented or synthesized."""

from abc import ABC, abstractmethod
import asyncio
import logging
from dataclasses import dataclass
from time import perf_counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.stock import Stock
from app.schemas.stock import StockHistoryPoint

logger = logging.getLogger("uvicorn.error")


class MarketDataError(Exception):
    def __init__(self, public_detail: str = "Market data is currently unavailable", status_code: int = 503, *, reason: str | None = None) -> None:
        super().__init__(public_detail)
        self.public_detail = public_detail
        self.status_code = status_code
        self.reason = reason


@dataclass(frozen=True)
class QuoteSnapshot:
    """A real provider quote plus the time it was obtained and its freshness."""

    price: Decimal
    as_of: datetime
    is_stale: bool = False


class MarketDataProvider(ABC):
    provider_name = "market"
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

    provider_name = "twelve"

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
            # httpx applies individual timeout values to connect/read/write/pool
            # phases. asyncio.wait_for adds the missing end-to-end budget for a
            # quote request, including DNS, connection, and response reading.
            timeout = httpx.Timeout(settings.market_data_timeout_seconds, connect=min(settings.market_data_timeout_seconds, 2.0))
            async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
                response = await asyncio.wait_for(
                    client.get(f"{self._base_url}{path}", params=params, headers=self._headers()),
                    timeout=settings.market_data_timeout_seconds,
                )
        except asyncio.TimeoutError as exc:
            raise MarketDataError("Market data provider timed out", reason="timeout") from exc
        except httpx.TimeoutException as exc:
            raise MarketDataError("Market data provider timed out", reason="timeout") from exc
        except httpx.HTTPError as exc:
            raise MarketDataError("Market data provider request failed", reason="request_failed") from exc
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
        normalized_query, _ = SymbolNormalizer.split(query)
        seen: set[tuple[str, str, str]] = set()
        candidates: list[tuple[dict, dict, int]] = []
        for source_index, item in enumerate(data):
            if not isinstance(item, dict) or not item.get("symbol"):
                continue
            raw_symbol = str(item["symbol"]).strip().upper()
            symbol, qualified_exchange = SymbolNormalizer.split(str(item["symbol"]))
            exchange = str(item.get("exchange") or qualified_exchange or "").strip().upper()
            currency = str(item.get("currency") or "").strip().upper()
            identity = (symbol, exchange, currency)
            if identity in seen:
                continue
            seen.add(identity)
            candidates.append((
                {
                    "symbol": raw_symbol,
                    "name": item.get("instrument_name") or item.get("name") or item["symbol"],
                    "exchange": exchange or None,
                    "currency": currency or "USD",
                },
                item,
                source_index,
            ))

        def rank(candidate: tuple[dict, dict, int]) -> tuple[int, int, int, int]:
            result, metadata, source_index = candidate
            symbol = SymbolNormalizer.split(result["symbol"])[0]
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

    async def history_for_days(self, symbol: str, days: int) -> list[StockHistoryPoint]:
        payload = await self._get("/time_series", {"symbol": symbol, "interval": "1day", "outputsize": str(max(30, min(days, 5000))), "order": "asc", "timezone": "UTC"})
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

    async def history(self, symbol: str) -> list[StockHistoryPoint]:
        return await self.history_for_days(symbol, 30)


class SymbolNormalizer:
    """Centralizes canonical listing identities and provider-specific symbols."""

    _EXCHANGE_ALIASES = {
        "NMS": "NASDAQ",
        "NASDAQGS": "NASDAQ",
        "NASDAQ GLOBAL SELECT MARKET": "NASDAQ",
        "NASDAQ CAPITAL MARKET": "NASDAQ",
        "NYQ": "NYSE",
        "NYSEARCA": "NYSE ARCA",
        "PCX": "NYSE ARCA",
        "ASE": "AMEX",
    }

    @staticmethod
    def split(symbol: str) -> tuple[str, str | None]:
        normalized = symbol.strip().upper()
        base, separator, exchange = normalized.partition(":")
        return base, exchange if separator and exchange else None

    @classmethod
    def exchange(cls, exchange: str | None) -> str:
        normalized = (exchange or "").strip().upper()
        return cls._EXCHANGE_ALIASES.get(normalized, normalized)

    @classmethod
    def listing(cls, symbol: str, exchange: str | None = None) -> tuple[str, str]:
        base, embedded_exchange = cls.split(symbol)
        return base, cls.exchange(exchange or embedded_exchange)

    @classmethod
    def twelve(cls, symbol: str, exchange: str | None = None) -> str:
        base, selected_exchange = cls.listing(symbol, exchange)
        return f"{base}:{selected_exchange}" if selected_exchange in {"NSE", "BSE"} else base

    @classmethod
    def yahoo(cls, symbol: str, exchange: str | None = None) -> str:
        base, selected_exchange = cls.listing(symbol, exchange)
        if selected_exchange == "NSE":
            return f"{base}.NS"
        if selected_exchange == "BSE":
            return f"{base}.BO"
        return base


def normalize_symbol(symbol: str) -> str:
    return SymbolNormalizer.split(symbol)[0]


def provider_symbol(symbol: str, exchange: str | None = None) -> str:
    return SymbolNormalizer.twelve(symbol, exchange)


class YahooFinanceProvider(MarketDataProvider):
    """Server-side yfinance adapter for exchange-aware quotes and history."""

    provider_name = "yahoo"

    def __init__(self, ticker_factory=None) -> None:
        self._ticker_factory = ticker_factory

    def _ticker(self, symbol: str):
        if self._ticker_factory is not None:
            return self._ticker_factory(symbol)
        try:
            import yfinance
        except ImportError as exc:  # Keeps startup explicit if requirements were not installed.
            raise MarketDataError("Market data provider is currently unavailable") from exc
        return yfinance.Ticker(symbol)

    async def search(self, query: str) -> list[dict]:
        # Search remains Twelve-only to avoid broad, costly fallback queries.
        raise MarketDataError("Stock data was not found", status_code=404)

    async def details(self, symbol: str) -> dict:
        base, exchange = SymbolNormalizer.listing(symbol)
        ticker = self._ticker(SymbolNormalizer.yahoo(base, exchange))
        try:
            info = await asyncio.to_thread(lambda: ticker.info)
        except Exception as exc:
            raise MarketDataError("Market data provider is currently unavailable") from exc
        if not isinstance(info, dict) or not info:
            raise MarketDataError("Stock data was not found", status_code=404)
        return {
            "symbol": base,
            "name": info.get("longName") or info.get("shortName") or base,
            "exchange": exchange or SymbolNormalizer.exchange(info.get("fullExchangeName") or info.get("exchange")),
            "currency": info.get("currency") or ("INR" if exchange in {"NSE", "BSE"} else "USD"),
        }

    async def quote(self, symbol: str) -> Decimal:
        ticker = self._ticker(SymbolNormalizer.yahoo(symbol))
        raw_price = None
        try:
            # `fast_info` resolves fields lazily in yfinance. Keep both its
            # creation and value access off FastAPI's event loop.
            raw_price = await asyncio.to_thread(
                lambda: ticker.fast_info.get("last_price") or ticker.fast_info.get("regular_market_price")
            )
            price = Decimal(str(raw_price)) if raw_price is not None else Decimal("0")
        except (Exception, InvalidOperation, TypeError):
            price = Decimal("0")
        # yfinance fast_info can omit or lazily fail to load current fields for
        # NSE/BSE listings. A latest valid Close is still real market data and
        # is the correct valuation reference while that market is closed.
        if price <= 0:
            try:
                frame = await asyncio.to_thread(lambda: ticker.history(period="5d", interval="1d", auto_adjust=False))
                closes = frame["Close"].dropna() if frame is not None and not frame.empty else []
                raw_price = closes.iloc[-1] if len(closes) else None
                price = Decimal(str(raw_price)) if raw_price is not None else Decimal("0")
            except (Exception, InvalidOperation, TypeError):
                price = Decimal("0")
        if price <= 0:
            raise MarketDataError("No current market price is available", status_code=404)
        return price

    async def history_for_days(self, symbol: str, days: int) -> list[StockHistoryPoint]:
        ticker_symbol = SymbolNormalizer.yahoo(symbol)
        ticker = self._ticker(ticker_symbol)
        period = "1y" if days > 35 else "1mo"
        started = perf_counter()
        try:
            frame = await asyncio.to_thread(lambda: ticker.history(period=period, interval="1d", auto_adjust=False))
            if frame is None or frame.empty:
                raise ValueError("empty history")
            closes = frame["Close"]
            # A single-ticker yfinance response is normally a Series. Accept a
            # one-column DataFrame too, but do not silently choose from a
            # multi-listing response.
            if getattr(closes, "ndim", 1) > 1:
                if closes.shape[1] != 1:
                    raise ValueError("ambiguous Close columns")
                closes = closes.iloc[:, 0]
            points: list[StockHistoryPoint] = []
            for index, raw_close in closes.items():
                try:
                    close = Decimal(str(raw_close))
                except (InvalidOperation, TypeError, ValueError):
                    continue
                # A current/incomplete market row can legitimately have a NaN
                # Close. It is not a provider-wide failure and must not discard
                # earlier daily closes.
                if not close.is_finite() or close <= 0:
                    continue
                timestamp = index.to_pydatetime()
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                points.append(StockHistoryPoint(timestamp=timestamp.astimezone(timezone.utc), close=close))
            if not points:
                raise ValueError("history contains no finite Close values")
            logger.info(
                "market_timing provider=yahoo method=Ticker.history symbol=%s ticker=%s period=%s interval=1d auto_adjust=false rows=%s valid_close_rows=%s first=%s last=%s latest_close=%s elapsed_ms=%.1f",
                symbol, ticker_symbol, period, len(frame), len(points), points[0].timestamp.isoformat(), points[-1].timestamp.isoformat(), points[-1].close,
                (perf_counter() - started) * 1000,
            )
            return points
        except Exception as exc:
            logger.warning(
                "market_timing provider=yahoo method=Ticker.history symbol=%s ticker=%s period=%s interval=1d auto_adjust=false error_type=%s error=%s elapsed_ms=%.1f",
                symbol, ticker_symbol, period, type(exc).__name__, str(exc), (perf_counter() - started) * 1000,
            )
            raise MarketDataError("Market data provider is currently unavailable", reason="yahoo_history_failed") from exc

    async def history(self, symbol: str) -> list[StockHistoryPoint]:
        return await self.history_for_days(symbol, 30)


class MarketDataService:
    def __init__(self, provider: MarketDataProvider, fallback_provider: MarketDataProvider | None = None) -> None:
        self.provider = provider
        self.fallback_provider = fallback_provider
        self._history_cache: dict[tuple[str, str, int], tuple[datetime, list[StockHistoryPoint]]] = {}
        # One provider request may serve every concurrent consumer of the same
        # listing/range. This complements (rather than replaces) the cache:
        # failed tasks never become cached historical data.
        self._history_tasks: dict[tuple[str, str, int], asyncio.Task[list[StockHistoryPoint]]] = {}
        self._quote_cache: dict[tuple[str, str], QuoteSnapshot] = {}
        self._quote_tasks: dict[tuple[str, str], asyncio.Task[QuoteSnapshot]] = {}
        self._primary_quote_unhealthy_until: datetime | None = None
        self._primary_quote_not_found_until: dict[str, datetime] = {}

    async def search(self, db: Session, query: str) -> list[Stock]:
        # Yahoo does not expose an equivalent low-cost symbol-search API. Its
        # immediate unsupported-search response is handled by the generic
        # fallback path, which delegates listing discovery to Twelve Data.
        results = await self._primary_or_fallback("search", query)
        stocks: list[Stock] = []
        seen_listings: set[tuple[str, str, str]] = set()
        for result in results:
            symbol, exchange = SymbolNormalizer.listing(result["symbol"], result.get("exchange"))
            currency = str(result.get("currency") or "").strip().upper()
            listing_identity = (symbol, exchange, currency)
            if listing_identity in seen_listings:
                continue
            seen_listings.add(listing_identity)
            self._upsert_stock(db, {**result, "symbol": symbol, "exchange": exchange, "currency": currency or "USD"})
            # Return the provider-facing selected listing, including `:NSE`
            # where present, while persisting the canonical pair separately.
            stocks.append(Stock(symbol=normalize_symbol(result["symbol"]), name=result.get("name") or symbol, exchange=exchange, currency=currency or "USD"))
        db.commit()
        return stocks

    def _upsert_stock(self, db: Session, data: dict) -> Stock:
        symbol, exchange = SymbolNormalizer.listing(data["symbol"], data.get("exchange"))
        stock = db.scalar(select(Stock).where(Stock.symbol == symbol, Stock.exchange == exchange))
        if stock is None:
            try:
                with db.begin_nested():
                    stock = Stock(
                        symbol=symbol,
                        name=data.get("name") or symbol,
                        exchange=exchange,
                        currency=data.get("currency") or "USD",
                    )
                    db.add(stock)
                    db.flush()
            except IntegrityError:
                stock = db.scalar(select(Stock).where(Stock.symbol == symbol, Stock.exchange == exchange))
                if stock is None:
                    raise
        else:
            stock.name = data.get("name") or stock.name
            stock.exchange = data.get("exchange") or stock.exchange
            stock.currency = data.get("currency") or stock.currency
        return stock

    async def _provider_operation(self, provider: MarketDataProvider, operation: str, symbol: str, *, days: int | None = None):
        method = getattr(provider, operation, None)
        if operation == "history_for_days":
            if method is not None:
                return await method(symbol, days)
            return await provider.history(symbol)
        return await getattr(provider, operation)(symbol)

    async def _primary_or_fallback(self, operation: str, symbol: str, *, days: int | None = None):
        started = perf_counter()
        primary_name = getattr(self.provider, "provider_name", self.provider.__class__.__name__.lower())
        fallback_name = getattr(self.fallback_provider, "provider_name", self.fallback_provider.__class__.__name__.lower()) if self.fallback_provider else None
        primary_on_cooldown = (
            operation == "quote"
            and self._primary_quote_unhealthy_until is not None
            and datetime.now(timezone.utc) < self._primary_quote_unhealthy_until
        )
        listing_not_found_until = self._primary_quote_not_found_until.get(symbol)
        listing_on_cooldown = (
            operation == "quote"
            and listing_not_found_until is not None
            and datetime.now(timezone.utc) < listing_not_found_until
        )
        if (primary_on_cooldown or listing_on_cooldown) and self.fallback_provider is not None:
            fallback_started = perf_counter()
            try:
                result = await self._provider_operation(self.fallback_provider, operation, symbol, days=days)
                logger.info(
                    "market_timing provider=%s operation=%s symbol=%s elapsed_ms=%.1f primary_cooldown=%s listing_not_found_cooldown=%s",
                    fallback_name, operation, symbol, (perf_counter() - fallback_started) * 1000, primary_on_cooldown, listing_on_cooldown,
                )
                return result
            except MarketDataError:
                # Do not retry a provider deliberately placed on cooldown.
                raise
        try:
            result = await self._provider_operation(self.provider, operation, symbol, days=days)
            logger.info("market_timing provider=%s operation=%s symbol=%s elapsed_ms=%.1f", primary_name, operation, symbol, (perf_counter() - started) * 1000)
            return result
        except MarketDataError as primary_error:
            logger.info("market_timing provider=%s operation=%s symbol=%s elapsed_ms=%.1f failed=true reason=%s", primary_name, operation, symbol, (perf_counter() - started) * 1000, primary_error.reason or primary_error.status_code)
            if operation == "quote" and primary_error.reason in {"timeout", "request_failed"}:
                self._primary_quote_unhealthy_until = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=settings.market_primary_cooldown_seconds)
            if operation == "quote" and primary_error.status_code == 404:
                self._primary_quote_not_found_until[symbol] = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=settings.market_primary_cooldown_seconds)
            if self.fallback_provider is None:
                raise
            try:
                fallback_started = perf_counter()
                result = await self._provider_operation(self.fallback_provider, operation, symbol, days=days)
                logger.info("market_timing provider=%s operation=%s symbol=%s elapsed_ms=%.1f", fallback_name, operation, symbol, (perf_counter() - fallback_started) * 1000)
                return result
            except MarketDataError:
                raise primary_error

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        """Normalize DB values without re-labelling non-UTC aware timestamps."""
        if value.tzinfo is None:
            # SQLite test databases return naive values; PostgreSQL returns aware
            # values for TIMESTAMP WITH TIME ZONE columns.
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    async def resolve_stock(self, db: Session, symbol: str, *, exchange: str | None = None) -> Stock:
        """Resolve and persist an instrument listing without obtaining a quote.

        This is used by the transaction ledger: recorded prices are supplied by
        the user and do not depend on a live valuation endpoint being healthy.
        """
        symbol, exchange = SymbolNormalizer.listing(symbol, exchange)
        selected_provider_symbol = provider_symbol(symbol, exchange)
        stock = db.scalar(select(Stock).where(Stock.symbol == symbol, Stock.exchange == exchange))
        if stock is None and not exchange:
            # Unqualified requests retain the already-resolved primary listing
            # rather than creating a duplicate blank-exchange cache row.
            stock = db.scalar(select(Stock).where(Stock.symbol == symbol).order_by(Stock.id))
            if stock is not None:
                exchange = stock.exchange
                selected_provider_symbol = provider_symbol(symbol, exchange)
        if stock is None:
            # The stock lookup above opened a read transaction. Return its
            # connection before provider I/O; loaded scalar values remain safe
            # because this session uses expire_on_commit=False.
            db.commit()
            details = await self._primary_or_fallback("details", selected_provider_symbol)
            details["symbol"], details["exchange"] = SymbolNormalizer.listing(
                details.get("symbol", symbol), details.get("exchange") or exchange
            )
            stock = self._upsert_stock(db, details)
            db.commit()
            db.refresh(stock)
        return stock

    async def get_stock(self, db: Session, symbol: str, *, exchange: str | None = None, require_price: bool = False) -> Stock:
        stock = await self.resolve_stock(db, symbol, exchange=exchange)
        stale = stock is None or stock.last_price_updated_at is None or (
            datetime.now(timezone.utc) - self._as_utc(stock.last_price_updated_at)
        ).total_seconds() > settings.market_cache_seconds
        if stale:
            # Do not hold a database connection while obtaining a remote quote.
            db.commit()
            try:
                snapshot = await self.quote_snapshot_for_stock(stock)
                # A stale snapshot is useful reference data but must retain its
                # original timestamp instead of being relabelled as current.
                if not snapshot.is_stale:
                    stock.last_price = snapshot.price
                    stock.last_price_updated_at = snapshot.as_of
            except MarketDataError:
                if require_price:
                    raise
            db.commit()
            db.refresh(stock)
        if require_price and (stock.last_price is None or stock.last_price <= 0):
            raise MarketDataError("No current market price is available")
        return stock

    def _quote_age_seconds(self, snapshot: QuoteSnapshot, now: datetime) -> float:
        return (now - self._as_utc(snapshot.as_of)).total_seconds()

    def _start_quote_refresh(self, key: tuple[str, str]) -> asyncio.Task[QuoteSnapshot]:
        task = self._quote_tasks.get(key)
        if task is None:
            async def refresh() -> QuoteSnapshot:
                price = await self._primary_or_fallback("quote", provider_symbol(*key))
                snapshot = QuoteSnapshot(
                    price=price.quantize(Decimal("0.000001")),
                    as_of=datetime.now(timezone.utc),
                )
                self._quote_cache[key] = snapshot
                return snapshot

            task = asyncio.create_task(refresh())
            self._quote_tasks[key] = task

            def clear_finished_task(completed: asyncio.Task[QuoteSnapshot]) -> None:
                if self._quote_tasks.get(key) is completed:
                    self._quote_tasks.pop(key, None)
                # Background stale refreshes have no awaiting request. Reading
                # the exception prevents an unobserved-task warning while the
                # last known real quote remains available.
                if not completed.cancelled():
                    try:
                        completed.exception()
                    except (asyncio.CancelledError, MarketDataError):
                        pass

            task.add_done_callback(clear_finished_task)
        return task

    async def quote_snapshot_for_stock(self, stock: Stock) -> QuoteSnapshot:
        """Return fresh data when available, otherwise a bounded stale real quote.

        A stale quote is only a previously provider-obtained value. It is never
        relabelled as fresh, and an asynchronous refresh is shared by all
        concurrent callers for the same exchange-aware listing.
        """
        key = (stock.symbol, stock.exchange)
        now = datetime.now(timezone.utc)
        candidates: list[tuple[str, QuoteSnapshot]] = []
        if stock.last_price is not None and stock.last_price_updated_at is not None:
            candidates.append(("db", QuoteSnapshot(stock.last_price, self._as_utc(stock.last_price_updated_at))))
        memory_snapshot = self._quote_cache.get(key)
        if memory_snapshot is not None:
            candidates.append(("memory", memory_snapshot))

        if candidates:
            source, snapshot = min(candidates, key=lambda item: self._quote_age_seconds(item[1], now))
            age_seconds = self._quote_age_seconds(snapshot, now)
            if age_seconds <= settings.market_cache_seconds:
                logger.info("market_timing quote_cache=%s symbol=%s exchange=%s freshness=fresh age_ms=%.1f", source, *key, age_seconds * 1000)
                return snapshot
            if age_seconds <= settings.market_stale_cache_seconds:
                logger.info("market_timing quote_cache=%s symbol=%s exchange=%s freshness=stale age_ms=%.1f", source, *key, age_seconds * 1000)
                self._start_quote_refresh(key)
                return QuoteSnapshot(snapshot.price, snapshot.as_of, is_stale=True)

        logger.info("market_timing quote_cache=miss symbol=%s exchange=%s", *key)
        return await asyncio.shield(self._start_quote_refresh(key))

    async def quote_for_stock(self, stock: Stock) -> Decimal:
        """Compatibility wrapper for consumers that only need the price."""
        return (await self.quote_snapshot_for_stock(stock)).price

    async def history(self, symbol: str, *, exchange: str | None = None) -> list[StockHistoryPoint]:
        return await self.history_for_days(symbol, exchange=exchange, days=30)

    @staticmethod
    def _history_range(points: list[StockHistoryPoint], days: int) -> list[StockHistoryPoint]:
        """Return the requested calendar range from a reusable wider series."""
        if not points:
            return []
        latest = max(
            point.timestamp.replace(tzinfo=timezone.utc) if point.timestamp.tzinfo is None else point.timestamp.astimezone(timezone.utc)
            for point in points
        )
        cutoff = latest - timedelta(days=days - 1)
        return [
            point for point in points
            if (point.timestamp.replace(tzinfo=timezone.utc) if point.timestamp.tzinfo is None else point.timestamp.astimezone(timezone.utc)) >= cutoff
        ]

    async def history_for_days(self, symbol: str, *, exchange: str | None = None, days: int = 30) -> list[StockHistoryPoint]:
        base, selected_exchange = SymbolNormalizer.listing(symbol, exchange)
        now = datetime.now(timezone.utc)
        for (cached_symbol, cached_exchange, cached_days), (cached_at, cached_points) in self._history_cache.items():
            if (cached_symbol, cached_exchange) == (base, selected_exchange) and cached_days >= days and (now - cached_at).total_seconds() <= settings.market_history_cache_seconds:
                return self._history_range(cached_points, days)

        # A wider in-flight series can satisfy a shorter consumer. Dashboard
        # startup requests the wider series first, but this also protects a
        # route hit at the same time from issuing the identical provider call.
        task_key = next(
            (key for key in self._history_tasks if key[0] == base and key[1] == selected_exchange and key[2] >= days),
            (base, selected_exchange, days),
        )
        task = self._history_tasks.get(task_key)
        if task is None:
            async def load_history() -> list[StockHistoryPoint]:
                points = await self._primary_or_fallback(
                    "history_for_days", provider_symbol(base, selected_exchange), days=days
                )
                # Only a successful provider result reaches the authoritative
                # history cache, so a failure cannot erase prior valid data.
                self._history_cache[(base, selected_exchange, days)] = (datetime.now(timezone.utc), points)
                return points

            task = asyncio.create_task(load_history())
            self._history_tasks[task_key] = task

            def clear_history_task(completed: asyncio.Task[list[StockHistoryPoint]]) -> None:
                if self._history_tasks.get(task_key) is completed:
                    self._history_tasks.pop(task_key, None)
                if not completed.cancelled():
                    try:
                        completed.exception()
                    except (asyncio.CancelledError, MarketDataError):
                        pass

            task.add_done_callback(clear_history_task)
        return self._history_range(await asyncio.shield(task), days)

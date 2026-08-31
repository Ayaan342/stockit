import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pandas as pd
import pytest

from app.models.stock import Stock
from app.services.market_data import MarketDataError, MarketDataProvider, MarketDataService, SymbolNormalizer, TwelveDataProvider, YahooFinanceProvider


def provider_with(handler) -> TwelveDataProvider:
    return TwelveDataProvider(transport=httpx.MockTransport(handler))


def test_twelve_data_search_preserves_indian_symbol_exchange_and_currency():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/symbol_search"
        assert request.url.params["symbol"] == "TCS"
        assert request.headers["Authorization"] == "apikey test-market-key"
        return httpx.Response(200, json={"data": [{"symbol": "TCS:NSE", "instrument_name": "Tata Consultancy Services", "exchange": "NSE", "currency": "INR"}]})

    result = asyncio.run(provider_with(handler).search("TCS"))
    assert result == [{"symbol": "TCS:NSE", "name": "Tata Consultancy Services", "exchange": "NSE", "currency": "INR"}]


def test_twelve_data_search_deduplicates_and_ranks_primary_common_stock_first():
    data = [
        {"symbol": "AAPL", "instrument_name": "Apple Inc.", "exchange": "SIX", "currency": "CHF", "country": "Switzerland", "type": "Common Stock"},
        {"symbol": "AAPL34", "instrument_name": "Apple structured note", "exchange": "B3", "currency": "BRL", "country": "Brazil", "type": "Structured Product"},
        {"symbol": "AAPL", "instrument_name": "Apple Inc.", "exchange": "NASDAQ", "currency": "USD", "country": "United States", "type": "Common Stock"},
        {"symbol": "AAPL", "instrument_name": "Apple Inc.", "exchange": "NASDAQ", "currency": "USD", "country": "United States", "type": "Common Stock"},
        {"symbol": "AAPLC", "instrument_name": "Apple depositary product", "exchange": "NASDAQ", "currency": "USD", "country": "United States", "type": "Depositary Receipt"},
    ]
    provider = provider_with(lambda request: httpx.Response(200, json={"data": data}))
    result = asyncio.run(provider.search("AAPL"))
    assert [(item["symbol"], item["exchange"], item["currency"]) for item in result] == [
        ("AAPL", "NASDAQ", "USD"),
        ("AAPL", "SIX", "CHF"),
        ("AAPL34", "B3", "BRL"),
        ("AAPLC", "NASDAQ", "USD"),
    ]


def test_twelve_data_search_preserves_indian_listings_and_qualified_symbols():
    data = [
        {"symbol": "TCS:NSE", "instrument_name": "Tata Consultancy Services", "exchange": "NSE", "currency": "INR", "country": "India", "type": "Common Stock"},
        {"symbol": "TCS:BSE", "instrument_name": "Tata Consultancy Services", "exchange": "BSE", "currency": "INR", "country": "India", "type": "Common Stock"},
        {"symbol": "TCS", "instrument_name": "Tata Consultancy Services ADR", "exchange": "NYSE", "currency": "USD", "country": "United States", "type": "Depositary Receipt"},
    ]
    provider = provider_with(lambda request: httpx.Response(200, json={"data": data}))
    india_results = asyncio.run(provider.search("TCS"))
    assert {(item["symbol"], item["exchange"]) for item in india_results} >= {("TCS:NSE", "NSE"), ("TCS:BSE", "BSE")}
    qualified_results = asyncio.run(provider.search("TCS:NSE"))
    assert qualified_results[0]["symbol"] == "TCS:NSE"


def test_twelve_data_search_limits_results_to_twenty():
    data = [
        {"symbol": f"AAP{index}", "instrument_name": f"Instrument {index}", "exchange": "NASDAQ", "currency": "USD", "country": "United States", "type": "Common Stock"}
        for index in range(25)
    ]
    provider = provider_with(lambda request: httpx.Response(200, json={"data": data}))
    assert len(asyncio.run(provider.search("AAP"))) == 20


def test_twelve_data_quote_is_decimal_and_reuses_detail_payload():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.path == "/quote"
        return httpx.Response(200, json={"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ", "currency": "USD", "close": "123.45"})

    provider = provider_with(handler)
    details = asyncio.run(provider.details("AAPL"))
    price = asyncio.run(provider.quote("AAPL"))
    assert details["exchange"] == "NASDAQ"
    assert str(price) == "123.45"
    assert calls == 1


def test_twelve_data_invalid_symbol_and_rate_limit_are_safe_errors():
    invalid = provider_with(lambda request: httpx.Response(200, json={"status": "error", "code": 400, "message": "invalid symbol"}))
    with pytest.raises(MarketDataError) as invalid_error:
        asyncio.run(invalid.details("NOPE"))
    assert invalid_error.value.status_code == 404

    limited = provider_with(lambda request: httpx.Response(429, json={"status": "error"}))
    with pytest.raises(MarketDataError) as limited_error:
        asyncio.run(limited.search("AAPL"))
    assert limited_error.value.status_code == 429


def test_twelve_data_history_normalizes_to_utc():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/time_series"
        assert request.url.params["interval"] == "1day"
        return httpx.Response(200, json={"meta": {"exchange_timezone": "Asia/Kolkata"}, "values": [{"datetime": "2026-08-25", "close": "3500.25"}]})

    points = asyncio.run(provider_with(handler).history("TCS:NSE"))
    assert str(points[0].close) == "3500.25"
    assert points[0].timestamp.tzinfo is not None
    assert points[0].timestamp.isoformat().endswith("+00:00")


def test_twelve_data_provider_failure_is_not_exposed():
    failing = provider_with(lambda request: httpx.Response(503, json={"message": "provider failure"}))
    with pytest.raises(MarketDataError) as error:
        asyncio.run(failing.quote("AAPL"))
    assert error.value.status_code == 503
    assert error.value.public_detail == "Market data provider is currently unavailable"


def test_twelve_data_enforces_an_end_to_end_timeout_budget():
    from app.core.config import settings

    async def delayed_handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.03)
        return httpx.Response(200, json={"symbol": "AAPL", "close": "123"})

    previous_timeout = settings.market_data_timeout_seconds
    settings.market_data_timeout_seconds = 0.01
    try:
        with pytest.raises(MarketDataError) as error:
            asyncio.run(provider_with(delayed_handler).quote("AAPL"))
        assert error.value.reason == "timeout"
    finally:
        settings.market_data_timeout_seconds = previous_timeout


def test_yahoo_fallback_is_conditional_and_uses_nse_suffix():
    class FailingPrimary(MarketDataProvider):
        async def search(self, query: str): raise MarketDataError(status_code=503)
        async def quote(self, symbol: str): raise MarketDataError(status_code=503)
        async def details(self, symbol: str): raise MarketDataError(status_code=503)
        async def history(self, symbol: str): raise MarketDataError(status_code=503)

    requested: list[str] = []
    class Ticker:
        fast_info = {"last_price": "3500.50"}
    fallback = YahooFinanceProvider(ticker_factory=lambda symbol: requested.append(symbol) or Ticker())
    service = MarketDataService(FailingPrimary(), fallback)
    assert asyncio.run(service._primary_or_fallback("quote", "TCS:NSE")) == Decimal("3500.50")
    assert requested == ["TCS.NS"]

    class DetailsTicker:
        info = {"longName": "Tata Consultancy Services", "currency": "INR"}
    details_requested: list[str] = []
    yahoo_details = YahooFinanceProvider(ticker_factory=lambda symbol: details_requested.append(symbol) or DetailsTicker())
    details = asyncio.run(yahoo_details.details("TCS:NSE"))
    assert details["exchange"] == "NSE"
    assert details_requested == ["TCS.NS"]


def test_yahoo_quote_uses_latest_real_close_when_fast_info_is_unavailable():
    class Ticker:
        fast_info = {}

        def history(self, **kwargs):
            return pd.DataFrame({"Close": [None, 3500.25]})

    requested: list[str] = []
    provider = YahooFinanceProvider(ticker_factory=lambda symbol: requested.append(symbol) or Ticker())
    assert asyncio.run(provider.quote("TCS:NSE")) == Decimal("3500.25")
    assert requested == ["TCS.NS"]


def test_successful_primary_does_not_call_yahoo_fallback():
    class Primary(MarketDataProvider):
        async def search(self, query: str): return []
        async def quote(self, symbol: str): return Decimal("123")
        async def details(self, symbol: str): return {}
        async def history(self, symbol: str): return []

    fallback = YahooFinanceProvider(ticker_factory=lambda symbol: (_ for _ in ()).throw(AssertionError("fallback called")))
    service = MarketDataService(Primary(), fallback)
    assert asyncio.run(service._primary_or_fallback("quote", "AAPL")) == Decimal("123")


def test_symbol_normalizer_keeps_exchange_aliases_provider_specific():
    assert SymbolNormalizer.twelve("TCS", "NSE") == "TCS:NSE"
    assert SymbolNormalizer.yahoo("TCS", "NSE") == "TCS.NS"
    assert SymbolNormalizer.yahoo("500325", "BSE") == "500325.BO"
    assert SymbolNormalizer.yahoo("AAPL", "NASDAQ") == "AAPL"


def test_concurrent_listing_quotes_share_one_provider_call():
    calls = 0

    class Provider(MarketDataProvider):
        async def search(self, query: str): return []
        async def details(self, symbol: str): return {}
        async def quote(self, symbol: str):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return Decimal("123.45")
        async def history(self, symbol: str): return []

    service = MarketDataService(Provider())
    first = Stock(symbol="AAPL", exchange="NASDAQ", name="Apple", currency="USD")
    second = Stock(symbol="AAPL", exchange="NASDAQ", name="Apple", currency="USD")
    async def resolve_both():
        return await asyncio.gather(service.quote_for_stock(first), service.quote_for_stock(second))

    prices = asyncio.run(resolve_both())
    assert prices == [Decimal("123.450000"), Decimal("123.450000")]
    assert calls == 1


def test_warm_listing_quote_cache_skips_a_second_provider_call():
    calls = 0

    class Provider(MarketDataProvider):
        async def search(self, query: str): return []
        async def details(self, symbol: str): return {}
        async def history(self, symbol: str): return []

        async def quote(self, symbol: str):
            nonlocal calls
            calls += 1
            return Decimal("123.45")

    service = MarketDataService(Provider())
    stock = Stock(symbol="AAPL", exchange="NASDAQ", name="Apple", currency="USD")

    async def resolve_twice():
        first = await service.quote_for_stock(stock)
        second = await service.quote_for_stock(stock)
        return first, second

    assert asyncio.run(resolve_twice()) == (Decimal("123.450000"), Decimal("123.450000"))
    assert calls == 1


def test_stale_real_quote_returns_immediately_and_shares_one_background_refresh():
    from app.core.config import settings

    calls = 0

    class Provider(MarketDataProvider):
        async def search(self, query: str): return []
        async def details(self, symbol: str): return {}
        async def history(self, symbol: str): return []

        async def quote(self, symbol: str):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return Decimal("125")

    previous_fresh = settings.market_cache_seconds
    previous_stale = settings.market_stale_cache_seconds
    settings.market_cache_seconds = 1
    settings.market_stale_cache_seconds = 60
    try:
        service = MarketDataService(Provider())
        stock = Stock(
            symbol="AAPL", exchange="NASDAQ", name="Apple", currency="USD",
            last_price=Decimal("123"), last_price_updated_at=datetime.now(timezone.utc) - timedelta(seconds=2),
        )

        async def resolve_stale_twice():
            first, second = await asyncio.gather(service.quote_snapshot_for_stock(stock), service.quote_snapshot_for_stock(stock))
            await asyncio.sleep(0.02)
            return first, second

        first, second = asyncio.run(resolve_stale_twice())
        assert first.price == Decimal("123") and first.is_stale is True
        assert second.price == Decimal("123") and second.is_stale is True
        assert calls == 1
    finally:
        settings.market_cache_seconds = previous_fresh
        settings.market_stale_cache_seconds = previous_stale


def test_twelve_listing_not_found_uses_yahoo_directly_on_the_next_quote():
    from app.core.config import settings

    primary_calls = 0
    fallback_calls = 0

    class Twelve(MarketDataProvider):
        async def search(self, query: str): return []
        async def details(self, symbol: str): return {}
        async def history(self, symbol: str): return []
        async def quote(self, symbol: str):
            nonlocal primary_calls
            primary_calls += 1
            raise MarketDataError("Stock data was not found", status_code=404)

    class Yahoo(MarketDataProvider):
        async def search(self, query: str): return []
        async def details(self, symbol: str): return {}
        async def history(self, symbol: str): return []
        async def quote(self, symbol: str):
            nonlocal fallback_calls
            fallback_calls += 1
            return Decimal("3500")

    previous_cooldown = settings.market_primary_cooldown_seconds
    settings.market_primary_cooldown_seconds = 30
    try:
        service = MarketDataService(Twelve(), Yahoo())
        assert asyncio.run(service._primary_or_fallback("quote", "TCS:NSE")) == Decimal("3500")
        assert asyncio.run(service._primary_or_fallback("quote", "TCS:NSE")) == Decimal("3500")
        assert primary_calls == 1
        assert fallback_calls == 2
    finally:
        settings.market_primary_cooldown_seconds = previous_cooldown

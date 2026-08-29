import httpx
from datetime import datetime, timezone
from decimal import Decimal

from tests.conftest import register_and_login


def test_detail_and_history_use_the_selected_listing_exchange(client):
    from app.main import app
    from app.schemas.stock import StockHistoryPoint
    from app.services.market_data import MarketDataProvider, MarketDataService

    class RecordingProvider(MarketDataProvider):
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def search(self, query: str) -> list[dict]:
            return []

        async def quote(self, symbol: str) -> Decimal:
            self.calls.append(f"quote:{symbol}")
            return Decimal("100")

        async def details(self, symbol: str) -> dict:
            self.calls.append(f"details:{symbol}")
            base, _, exchange = symbol.partition(":")
            return {"symbol": base, "name": base, "exchange": exchange or "NASDAQ", "currency": "USD"}

        async def history(self, symbol: str) -> list[StockHistoryPoint]:
            self.calls.append(f"history:{symbol}")
            return [StockHistoryPoint(timestamp=datetime.now(timezone.utc), close=Decimal("100"))]

    provider = RecordingProvider()
    app.state.market_service = MarketDataService(provider)
    listings = [
        ("AAPL", "NASDAQ"),
        ("TCS", "NSE"),
        ("RELIANCE", "NSE"),
        ("M&M", "NSE"),
        ("AAPL", "NEO"),
        ("TCS:NSE", "NSE"),
    ]
    for symbol, exchange in listings:
        detail = client.get(f"/api/v1/stocks/{symbol}", params={"exchange": exchange})
        history = client.get(f"/api/v1/stocks/{symbol}/history", params={"exchange": exchange})
        assert detail.status_code == history.status_code == 200
        expected = symbol if ":" in symbol else f"{symbol}:{exchange}"
        assert f"details:{expected}" in provider.calls
        assert f"history:{expected}" in provider.calls


def test_stock_detail_preserves_market_rate_limit_status(client):
    from app.main import app
    from app.services.market_data import MarketDataError, MarketDataProvider, MarketDataService

    class LimitedProvider(MarketDataProvider):
        async def search(self, query: str) -> list[dict]:
            raise MarketDataError("Market data rate limit reached", status_code=429)

        async def quote(self, symbol: str) -> Decimal:
            raise MarketDataError("Market data rate limit reached", status_code=429)

        async def details(self, symbol: str) -> dict:
            raise MarketDataError("Market data rate limit reached", status_code=429)

        async def history(self, symbol: str):
            raise MarketDataError("Market data rate limit reached", status_code=429)

    app.state.market_service = MarketDataService(LimitedProvider())
    response = client.get("/api/v1/stocks/AAPL", params={"exchange": "NASDAQ"})
    assert response.status_code == 429


def test_stock_lookup_search_and_history(client):
    assert client.get("/api/v1/stocks/search", params={"q": "AAP"}).status_code == 200
    detail = client.get("/api/v1/stocks/AAPL")
    assert detail.status_code == 200
    assert detail.json()["last_price"] == "100.000000"
    assert len(client.get("/api/v1/stocks/AAPL/history").json()) == 2


def test_stock_detail_uses_the_existing_market_cache(client):
    from app.main import app

    first = client.get("/api/v1/stocks/AAPL")
    second = client.get("/api/v1/stocks/AAPL")
    assert first.status_code == second.status_code == 200
    assert app.state.market_service.provider.quote_calls == 1


def test_stock_search_route_keeps_distinct_listings_after_database_caching(client):
    from app.main import app
    from app.services.market_data import MarketDataService, TwelveDataProvider

    duplicate_neo = {
        "symbol": "AAPL",
        "instrument_name": "Apple Inc.",
        "exchange": "NEO",
        "currency": "CAD",
        "country": "Canada",
        "type": "Common Stock",
    }
    nasdaq = {
        "symbol": "AAPL",
        "instrument_name": "Apple Inc.",
        "exchange": "NASDAQ",
        "currency": "USD",
        "country": "United States",
        "type": "Common Stock",
    }
    provider = TwelveDataProvider(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"data": [duplicate_neo] * 10 + [nasdaq]})))
    app.state.market_service = MarketDataService(provider)

    response = client.get("/api/v1/stocks/search", params={"q": "AAPL"})
    assert response.status_code == 200
    listings = response.json()
    assert [(item["symbol"], item["exchange"], item["currency"]) for item in listings] == [
        ("AAPL", "NASDAQ", "USD"),
        ("AAPL", "NEO", "CAD"),
    ]


def test_watchlist_add_remove_and_duplicate(client):
    headers = register_and_login(client)
    created = client.post("/api/v1/watchlists", json={"name": "Tech"}, headers=headers)
    assert created.status_code == 201
    watchlist_id = created.json()["id"]
    added = client.post(f"/api/v1/watchlists/{watchlist_id}/stocks/AAPL", headers=headers)
    assert added.status_code == 201
    duplicate = client.post(f"/api/v1/watchlists/{watchlist_id}/stocks/AAPL", headers=headers)
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Stock is already in this watchlist"
    assert client.delete(f"/api/v1/watchlists/{watchlist_id}/stocks/AAPL", headers=headers).status_code == 204

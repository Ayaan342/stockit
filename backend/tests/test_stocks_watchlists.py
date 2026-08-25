import httpx

from tests.conftest import register_and_login


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

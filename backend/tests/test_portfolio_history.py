from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.schemas.stock import StockHistoryPoint
from app.services.market_data import MarketDataProvider, MarketDataService
from tests.conftest import register_and_login


class HistoryProvider(MarketDataProvider):
    def __init__(self, *, skip_weekends: bool = False) -> None:
        self.calls: list[str] = []
        self.skip_weekends = skip_weekends

    async def search(self, query: str): return []
    async def quote(self, symbol: str): return Decimal("100")

    async def details(self, symbol: str):
        base, _, exchange = symbol.partition(":")
        return {"symbol": base, "name": base, "exchange": exchange or "NASDAQ", "currency": "INR" if exchange in {"NSE", "BSE"} else "USD"}

    async def history(self, symbol: str):
        self.calls.append(symbol)
        now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        return [
            StockHistoryPoint(timestamp=now - timedelta(days=offset), close=Decimal("100" if symbol == "AAPL" else "3000"))
            for offset in range(405) if not self.skip_weekends or (now - timedelta(days=offset)).weekday() < 5
        ]


def trade(client, headers, side: str, symbol: str, quantity: str, price: str, days_ago: int, exchange: str | None = None):
    payload = {"symbol": symbol, "quantity": quantity, "price": price, "executed_at": (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()}
    if exchange:
        payload["exchange"] = exchange
    response = client.post(f"/api/v1/portfolio/{side}", json=payload, headers=headers)
    assert response.status_code == 201, response.text


def test_history_replays_buys_partial_and_full_sells(client):
    from app.main import app
    provider = HistoryProvider()
    app.state.market_service = MarketDataService(provider)
    headers = register_and_login(client)
    trade(client, headers, "buy", "AAPL", "10", "90", 35)  # owned before the chart range
    trade(client, headers, "sell", "AAPL", "4", "95", 15)
    response = client.get("/api/v1/portfolio/history?currency=USD&period=30d", headers=headers)
    assert response.status_code == 200, response.text
    points = response.json()["points"]
    assert Decimal(points[0]["value"]) == Decimal("1000.00")
    assert Decimal(points[-16]["value"]) == Decimal("600.00")
    trade(client, headers, "sell", "AAPL", "6", "100", 5)
    refreshed = client.get("/api/v1/portfolio/history?currency=USD&period=30d", headers=headers).json()["points"]
    assert Decimal(refreshed[-6]["value"]) == Decimal("0.00")


def test_history_separates_inr_and_uses_nse_listing_identity(client):
    from app.main import app
    provider = HistoryProvider()
    app.state.market_service = MarketDataService(provider)
    headers = register_and_login(client)
    trade(client, headers, "buy", "AAPL", "2", "100", 10)
    trade(client, headers, "buy", "TCS", "3", "3000", 10, "NSE")
    inr = client.get("/api/v1/portfolio/history?currency=INR&period=30d", headers=headers)
    usd = client.get("/api/v1/portfolio/history?currency=USD&period=30d", headers=headers)
    assert inr.status_code == usd.status_code == 200
    assert Decimal(inr.json()["points"][-1]["value"]) == Decimal("9000.00")
    assert Decimal(usd.json()["points"][-1]["value"]) == Decimal("200.00")
    assert "TCS:NSE" in provider.calls and "AAPL" in provider.calls


def test_history_carries_forward_real_closes_over_missing_market_days(client):
    from app.main import app
    provider = HistoryProvider(skip_weekends=True)
    app.state.market_service = MarketDataService(provider)
    headers = register_and_login(client)
    trade(client, headers, "buy", "AAPL", "1", "100", 28)
    response = client.get("/api/v1/portfolio/history?currency=USD&period=30d", headers=headers)
    assert response.status_code == 200
    values = [Decimal(point["value"]) for point in response.json()["points"] if point["value"] is not None]
    assert Decimal("0.00") in values  # before the first BUY in the range
    assert all(value in {Decimal("0.00"), Decimal("100.00")} for value in values)


def test_history_cache_reuses_broader_series_for_shorter_period(client):
    from app.main import app
    provider = HistoryProvider()
    app.state.market_service = MarketDataService(provider)
    headers = register_and_login(client)
    trade(client, headers, "buy", "AAPL", "1", "100", 10)
    assert client.get("/api/v1/portfolio/history?currency=USD&period=1y", headers=headers).status_code == 200
    assert client.get("/api/v1/portfolio/history?currency=USD&period=30d", headers=headers).status_code == 200
    assert provider.calls == ["AAPL"]

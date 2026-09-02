import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.core.config import settings
from app.schemas.stock import StockHistoryPoint
from app.services.market_data import MarketDataError, MarketDataProvider, MarketDataService
from app.services.portfolio_history import _market_date
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


class NseReplayProvider(MarketDataProvider):
    """NSE closes normalized by Yahoo from local midnight to UTC."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def search(self, query: str): return []
    async def quote(self, symbol: str): return Decimal("1")

    async def details(self, symbol: str):
        base, _, exchange = symbol.partition(":")
        return {"symbol": base, "name": base, "exchange": exchange, "currency": "INR"}

    async def history(self, symbol: str):
        self.calls.append(symbol)
        closes = {
            "TCS:NSE": [
                ("2026-08-27T18:30:00+00:00", "2342"),
                ("2026-08-30T18:30:00+00:00", "2399.3"),
                ("2026-08-31T18:30:00+00:00", "2369"),
            ],
            "M&M:NSE": [
                ("2026-08-27T18:30:00+00:00", "3334"),
                ("2026-08-30T18:30:00+00:00", "3282"),
                ("2026-08-31T18:30:00+00:00", "3259"),
            ],
        }[symbol]
        return [
            StockHistoryPoint(timestamp=datetime.fromisoformat(raw_timestamp), close=Decimal(raw_close))
            for raw_timestamp, raw_close in closes
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


def test_warm_nse_history_cache_avoids_a_second_provider_request_for_each_listing():
    provider = HistoryProvider()
    service = MarketDataService(provider)

    async def load_twice():
        await asyncio.gather(
            service.history_for_days("TCS", exchange="NSE", days=400),
            service.history_for_days("M&M", exchange="NSE", days=400),
        )
        await asyncio.gather(
            service.history_for_days("TCS", exchange="NSE", days=400),
            service.history_for_days("M&M", exchange="NSE", days=400),
        )

    asyncio.run(load_twice())
    assert provider.calls.count("TCS:NSE") == 1
    assert provider.calls.count("M&M:NSE") == 1


def test_history_inflight_deduplicates_a_broader_series_for_a_shorter_consumer():
    provider = HistoryProvider()
    service = MarketDataService(provider)

    async def resolve_both():
        return await asyncio.gather(
            service.history_for_days("AAPL", exchange="NASDAQ", days=400),
            service.history_for_days("AAPL", exchange="NASDAQ", days=45),
        )

    wide, short = asyncio.run(resolve_both())
    assert provider.calls == ["AAPL"]
    assert len(wide) == 400
    assert len(short) == 45
    assert short == wide[:45]


def test_failed_history_refresh_does_not_overwrite_a_previously_valid_cache_entry():
    class FailingAfterFirstHistory(HistoryProvider):
        async def history(self, symbol: str):
            if self.calls:
                raise MarketDataError("Market data is currently unavailable")
            return await super().history(symbol)

    provider = FailingAfterFirstHistory()
    service = MarketDataService(provider)
    initial = asyncio.run(service.history_for_days("AAPL", exchange="NASDAQ", days=30))
    key = ("AAPL", "NASDAQ", 30)
    service._history_cache[key] = (
        datetime.now(timezone.utc) - timedelta(seconds=settings.market_history_cache_seconds + 1),
        initial,
    )

    with pytest.raises(MarketDataError):
        asyncio.run(service.history_for_days("AAPL", exchange="NASDAQ", days=30))

    assert service._history_cache[key][1] == initial


def test_nse_trade_and_daily_close_keep_the_india_market_date():
    # A local Aug 31 transaction and local-midnight daily close both appear as
    # Aug 30 in UTC. Replay must use the NSE calendar date instead.
    trade_time = datetime(2026, 8, 31, 1, 53, tzinfo=ZoneInfo("Asia/Kolkata"))
    close_as_utc = datetime(2026, 8, 30, 18, 30, tzinfo=timezone.utc)

    assert _market_date(trade_time, "NSE") == date(2026, 8, 31)
    assert _market_date(close_as_utc, "NSE") == date(2026, 8, 31)


def test_nse_history_uses_prior_close_for_sunday_ownership_and_market_date_keys(client):
    from app.main import app

    provider = NseReplayProvider()
    market = MarketDataService(provider)
    app.state.market_service = market
    headers = register_and_login(client)

    def record(side: str, symbol: str, quantity: str, price: str, executed_at: str):
        response = client.post(
            f"/api/v1/portfolio/{side}",
            json={"symbol": symbol, "exchange": "NSE", "quantity": quantity, "price": price, "executed_at": executed_at},
            headers=headers,
        )
        assert response.status_code == 201, response.text

    # TCS is first owned on Sunday, after Friday's final close. M&M becomes a
    # one-share position on Monday after its same-day buy and partial sell.
    record("buy", "TCS", "10", "3000", "2026-08-30T15:30:00+05:30")
    record("buy", "TCS", "5", "3300", "2026-08-30T15:35:00+05:30")
    record("sell", "TCS", "5", "3600", "2026-08-30T15:45:00+05:30")
    record("buy", "M&M", "2", "3334", "2026-08-31T01:53:00+05:30")
    record("sell", "M&M", "1", "3000", "2026-08-31T01:54:00+05:30")

    response = client.get("/api/v1/portfolio/history?currency=INR&period=1y", headers=headers)
    assert response.status_code == 200, response.text
    values = {point["date"]: Decimal(point["value"]) if point["value"] is not None else None for point in response.json()["points"]}

    assert values["2026-08-28"] == Decimal("0.00")  # no ownership before Sunday
    assert values["2026-08-30"] == Decimal("23420.00")  # 10 TCS × Friday close 2342
    assert values["2026-08-31"] == Decimal("27275.00")  # 10 × 2399.3 + 1 × 3282
    assert values["2026-09-01"] == Decimal("26949.00")  # 10 × 2369 + 1 × 3259

    # The history cache keeps UTC timestamps, but both cache inspection and
    # portfolio lookup use the exchange-local NSE calendar date.
    tcs_cached = market._history_cache[("TCS", "NSE", 400)][1]
    assert [_market_date(point.timestamp, "NSE") for point in tcs_cached] == [
        date(2026, 8, 28), date(2026, 8, 31), date(2026, 9, 1)
    ]
    assert provider.calls.count("TCS:NSE") == 1
    assert provider.calls.count("M&M:NSE") == 1

from decimal import Decimal

from tests.conftest import register_and_login


def set_price(client, symbol: str, price: str) -> None:
    from app.core.config import settings
    from app.main import app

    app.state.market_service.provider.prices[symbol] = Decimal(price)
    settings.market_cache_seconds = 0


def test_buy_sell_holdings_and_transaction_history(client):
    headers = register_and_login(client)
    buy = client.post("/api/v1/portfolio/buy", json={"symbol": "AAPL", "quantity": "2", "price": "100"}, headers=headers)
    assert buy.status_code == 201, buy.text
    holdings = client.get("/api/v1/portfolio/holdings", headers=headers)
    assert holdings.json()[0]["quantity"] == "2.000000"
    sell = client.post("/api/v1/portfolio/sell", json={"symbol": "AAPL", "quantity": "1", "price": "100"}, headers=headers)
    assert sell.status_code == 201, sell.text
    transactions = client.get("/api/v1/portfolio/transactions", headers=headers)
    assert [item["transaction_type"] for item in transactions.json()] == ["SELL", "BUY"]


def test_manual_buy_and_overselling(client):
    headers = register_and_login(client)
    assert client.post("/api/v1/portfolio/buy", json={"symbol": "MSFT", "quantity": "10", "price": "200"}, headers=headers).status_code == 201
    assert client.post("/api/v1/portfolio/buy", json={"symbol": "AAPL", "quantity": "2", "price": "100"}, headers=headers).status_code == 201
    assert client.post("/api/v1/portfolio/sell", json={"symbol": "AAPL", "quantity": "3", "price": "100"}, headers=headers).status_code == 400


def test_average_price_summary_and_profit_loss(client):
    headers = register_and_login(client)
    assert client.post("/api/v1/portfolio/buy", json={"symbol": "AAPL", "quantity": "2", "price": "100"}, headers=headers).status_code == 201
    set_price(client, "AAPL", "120.00")
    assert client.post("/api/v1/portfolio/buy", json={"symbol": "AAPL", "quantity": "1", "price": "120"}, headers=headers).status_code == 201
    summary = client.get("/api/v1/portfolio", headers=headers)
    assert summary.status_code == 200, summary.text
    data = summary.json()
    assert Decimal(data["current_holdings_value"]) == Decimal("360.00")
    assert Decimal(data["total_profit_loss"]) == Decimal("40.00")
    holding = client.get("/api/v1/portfolio/holdings", headers=headers).json()[0]
    assert Decimal(holding["average_buy_price"]) == Decimal("106.666667")
    from app.core.config import settings
    settings.market_cache_seconds = 60


def test_partial_sale_tracks_realized_and_remaining_unrealized_profit_loss(client):
    headers = register_and_login(client)
    assert client.post("/api/v1/portfolio/buy", json={"symbol": "AAPL", "quantity": "10", "price": "100"}, headers=headers).status_code == 201
    set_price(client, "AAPL", "150.00")
    assert client.post("/api/v1/portfolio/sell", json={"symbol": "AAPL", "quantity": "4", "price": "150"}, headers=headers).status_code == 201
    data = client.get("/api/v1/portfolio", headers=headers).json()
    assert Decimal(data["realized_profit_loss"]) == Decimal("200.00")
    assert Decimal(data["unrealized_profit_loss"]) == Decimal("300.00")
    assert Decimal(data["total_profit_loss"]) == Decimal("500.00")
    assert Decimal(client.get("/api/v1/portfolio/holdings", headers=headers).json()[0]["quantity"]) == Decimal("6.000000")
    from app.core.config import settings
    settings.market_cache_seconds = 60


def test_full_profitable_sale_keeps_realized_profit_loss(client):
    headers = register_and_login(client)
    assert client.post("/api/v1/portfolio/buy", json={"symbol": "AAPL", "quantity": "10", "price": "100"}, headers=headers).status_code == 201
    set_price(client, "AAPL", "150.00")
    assert client.post("/api/v1/portfolio/sell", json={"symbol": "AAPL", "quantity": "10", "price": "150"}, headers=headers).status_code == 201
    data = client.get("/api/v1/portfolio", headers=headers).json()
    assert Decimal(data["realized_profit_loss"]) == Decimal("500.00")
    assert Decimal(data["unrealized_profit_loss"]) == Decimal("0.00")
    assert Decimal(data["total_profit_loss"]) == Decimal("500.00")
    from app.core.config import settings
    settings.market_cache_seconds = 60


def test_full_losing_sale_tracks_negative_realized_profit_loss(client):
    headers = register_and_login(client)
    assert client.post("/api/v1/portfolio/buy", json={"symbol": "AAPL", "quantity": "10", "price": "100"}, headers=headers).status_code == 201
    set_price(client, "AAPL", "80.00")
    assert client.post("/api/v1/portfolio/sell", json={"symbol": "AAPL", "quantity": "10", "price": "80"}, headers=headers).status_code == 201
    data = client.get("/api/v1/portfolio", headers=headers).json()
    assert Decimal(data["realized_profit_loss"]) == Decimal("-200.00")
    assert Decimal(data["total_profit_loss"]) == Decimal("-200.00")
    from app.core.config import settings
    settings.market_cache_seconds = 60


def test_fees_are_included_in_weighted_cost_and_net_sell_proceeds(client):
    headers = register_and_login(client)
    buy = client.post("/api/v1/portfolio/buy", json={"symbol": "AAPL", "quantity": "2", "price": "100", "fees": "10"}, headers=headers)
    assert buy.status_code == 201
    assert buy.json()["price"] == "100.000000"
    set_price(client, "AAPL", "120")
    sell = client.post("/api/v1/portfolio/sell", json={"symbol": "AAPL", "quantity": "1", "price": "120", "fees": "5"}, headers=headers)
    assert sell.status_code == 201
    data = client.get("/api/v1/portfolio", headers=headers).json()
    # Cost/share is 105; net sale proceeds are 115.
    assert Decimal(data["realized_profit_loss"]) == Decimal("10.00")
    assert Decimal(data["unrealized_profit_loss"]) == Decimal("15.00")
    assert Decimal(data["total_profit_loss"]) == Decimal("25.00")
    from app.core.config import settings
    settings.market_cache_seconds = 60


def test_currency_groups_and_allocation_never_mix_inr_and_usd(client):
    headers = register_and_login(client)
    assert client.post("/api/v1/portfolio/buy", json={"symbol": "AAPL", "quantity": "1", "price": "100"}, headers=headers).status_code == 201
    assert client.post("/api/v1/portfolio/buy", json={"symbol": "TCS", "exchange": "NSE", "quantity": "2", "price": "3000"}, headers=headers).status_code == 201
    summary = client.get("/api/v1/portfolio", headers=headers).json()
    groups = {group["currency"]: group for group in summary["groups"]}
    assert groups["USD"]["total_portfolio_value"] == "100.00"
    assert groups["INR"]["total_portfolio_value"] == "7000.00"
    assert summary["total_portfolio_value"] is None
    holdings = client.get("/api/v1/portfolio/holdings", headers=headers).json()
    assert {item["currency"] for item in holdings} == {"USD", "INR"}
    assert all(Decimal(item["allocation_percentage"]) == Decimal("100.00") for item in holdings)


def test_manual_buy_resolves_nse_listing_with_fallback_without_a_live_quote(client):
    from app.main import app
    from app.services.market_data import MarketDataError, MarketDataProvider, MarketDataService

    primary_calls: list[str] = []
    fallback_calls: list[str] = []

    class TwelveUnavailable(MarketDataProvider):
        async def search(self, query: str): return []
        async def details(self, symbol: str):
            primary_calls.append(symbol)
            raise MarketDataError("Stock data was not found", status_code=404)
        async def quote(self, symbol: str): raise AssertionError("trade must not request a quote")
        async def history(self, symbol: str): return []

    class YahooResolved(MarketDataProvider):
        async def search(self, query: str): return []
        async def details(self, symbol: str):
            fallback_calls.append(symbol)
            base, _, exchange = symbol.partition(":")
            return {"symbol": base, "name": f"{base} Ltd", "exchange": exchange, "currency": "INR"}
        async def quote(self, symbol: str): raise AssertionError("trade must not request a quote")
        async def history(self, symbol: str): return []

    app.state.market_service = MarketDataService(TwelveUnavailable(), YahooResolved())
    headers = register_and_login(client)
    response = client.post("/api/v1/portfolio/buy", json={
        "symbol": "TCS", "exchange": "NSE", "quantity": "10", "price": "3000",
        "fees": "0", "executed_at": "2026-08-30T10:00:00Z", "notes": "First TCS buy",
    }, headers=headers)
    assert response.status_code == 201, response.text
    assert response.json()["price"] == "3000.000000"
    assert response.json()["exchange"] == "NSE"
    assert primary_calls == ["TCS:NSE"]
    assert fallback_calls == ["TCS:NSE"]


def test_listing_resolution_handles_nse_bse_us_and_invalid_instruments(client):
    from app.main import app
    from app.services.market_data import MarketDataError, MarketDataProvider, MarketDataService

    class Primary(MarketDataProvider):
        async def search(self, query: str): return []
        async def details(self, symbol: str): raise MarketDataError("Stock data was not found", status_code=404)
        async def quote(self, symbol: str): raise AssertionError("trade must not request a quote")
        async def history(self, symbol: str): return []

    class Fallback(MarketDataProvider):
        async def search(self, query: str): return []
        async def details(self, symbol: str):
            if symbol.startswith("NOPE"):
                raise MarketDataError("Stock data was not found", status_code=404)
            base, _, exchange = symbol.partition(":")
            return {"symbol": base, "name": base, "exchange": exchange or "NASDAQ", "currency": "INR" if exchange in {"NSE", "BSE"} else "USD"}
        async def quote(self, symbol: str): raise AssertionError("trade must not request a quote")
        async def history(self, symbol: str): return []

    app.state.market_service = MarketDataService(Primary(), Fallback())
    headers = register_and_login(client)
    for symbol, exchange in [("RELIANCE", "NSE"), ("M&M", "NSE"), ("500325", "BSE"), ("AAPL", "NASDAQ")]:
        response = client.post("/api/v1/portfolio/buy", json={"symbol": symbol, "exchange": exchange, "quantity": "1", "price": "1"}, headers=headers)
        assert response.status_code == 201, response.text
        assert response.json()["exchange"] == exchange
    missing = client.post("/api/v1/portfolio/buy", json={"symbol": "NOPE", "exchange": "NSE", "quantity": "1", "price": "1"}, headers=headers)
    assert missing.status_code == 404


def test_holdings_keep_recorded_positions_when_one_quote_is_unavailable(client):
    from app.main import app
    from app.services.market_data import MarketDataError, MarketDataProvider, MarketDataService

    class SelectiveQuotes(MarketDataProvider):
        async def search(self, query: str): return []
        async def details(self, symbol: str):
            base, _, exchange = symbol.partition(":")
            return {"symbol": base, "name": f"{base} Inc.", "exchange": exchange or "NASDAQ", "currency": "INR" if exchange == "NSE" else "USD"}
        async def quote(self, symbol: str):
            if symbol == "TCS:NSE":
                raise MarketDataError("Market data provider is currently unavailable", status_code=503)
            return Decimal("150")
        async def history(self, symbol: str): return []

    app.state.market_service = MarketDataService(SelectiveQuotes())
    headers = register_and_login(client)
    assert client.post("/api/v1/portfolio/buy", json={"symbol": "AAPL", "exchange": "NASDAQ", "quantity": "2", "price": "100"}, headers=headers).status_code == 201
    assert client.post("/api/v1/portfolio/buy", json={"symbol": "TCS", "exchange": "NSE", "quantity": "3", "price": "3000"}, headers=headers).status_code == 201
    assert client.post("/api/v1/portfolio/sell", json={"symbol": "TCS", "exchange": "NSE", "quantity": "1", "price": "3100"}, headers=headers).status_code == 201

    response = client.get("/api/v1/portfolio/holdings", headers=headers)
    assert response.status_code == 200, response.text
    holdings = {item["symbol"]: item for item in response.json()}
    assert holdings["AAPL"]["current_market_price"] == "150.000000"
    failed = holdings["TCS"]
    assert failed["exchange"] == "NSE"
    assert failed["quantity"] == "2.000000"
    assert failed["average_buy_price"] == "3000.000000"
    assert failed["invested_value"] == "6000.00"
    assert failed["current_market_price"] is None
    assert failed["current_value"] is None
    assert failed["profit_loss"] is None
    assert failed["profit_loss_percentage"] is None
    assert failed["allocation_percentage"] is None
    summary = client.get("/api/v1/portfolio", headers=headers)
    assert summary.status_code == 200, summary.text
    groups = {item["currency"]: item for item in summary.json()["groups"]}
    assert groups["USD"]["current_holdings_value"] == "300.00"
    assert groups["INR"]["total_invested"] == "6000.00"
    assert groups["INR"]["realized_profit_loss"] == "100.00"
    assert groups["INR"]["current_holdings_value"] is None
    assert groups["INR"]["unrealized_profit_loss"] is None
    assert groups["INR"]["total_portfolio_value"] is None
    assert groups["INR"]["total_profit_loss"] is None
    assert groups["INR"]["profit_loss_percentage"] is None

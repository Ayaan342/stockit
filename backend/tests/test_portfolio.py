from decimal import Decimal

from tests.conftest import register_and_login


def set_price(client, symbol: str, price: str) -> None:
    from app.core.config import settings
    from app.main import app

    app.state.market_service.provider.prices[symbol] = Decimal(price)
    settings.market_cache_seconds = 0


def test_buy_sell_holdings_and_transaction_history(client):
    headers = register_and_login(client)
    buy = client.post("/api/v1/portfolio/buy", json={"symbol": "AAPL", "quantity": "2"}, headers=headers)
    assert buy.status_code == 201, buy.text
    holdings = client.get("/api/v1/portfolio/holdings", headers=headers)
    assert holdings.json()[0]["quantity"] == "2.000000"
    sell = client.post("/api/v1/portfolio/sell", json={"symbol": "AAPL", "quantity": "1"}, headers=headers)
    assert sell.status_code == 201, sell.text
    transactions = client.get("/api/v1/portfolio/transactions", headers=headers)
    assert [item["transaction_type"] for item in transactions.json()] == ["SELL", "BUY"]


def test_insufficient_cash_and_overselling(client):
    headers = register_and_login(client)
    assert client.post("/api/v1/portfolio/buy", json={"symbol": "MSFT", "quantity": "10"}, headers=headers).status_code == 400
    assert client.post("/api/v1/portfolio/buy", json={"symbol": "AAPL", "quantity": "2"}, headers=headers).status_code == 201
    assert client.post("/api/v1/portfolio/sell", json={"symbol": "AAPL", "quantity": "3"}, headers=headers).status_code == 400


def test_average_price_summary_and_profit_loss(client):
    headers = register_and_login(client)
    assert client.post("/api/v1/portfolio/buy", json={"symbol": "AAPL", "quantity": "2"}, headers=headers).status_code == 201
    set_price(client, "AAPL", "120.00")
    assert client.post("/api/v1/portfolio/buy", json={"symbol": "AAPL", "quantity": "1"}, headers=headers).status_code == 201
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
    assert client.post("/api/v1/portfolio/buy", json={"symbol": "AAPL", "quantity": "10"}, headers=headers).status_code == 201
    set_price(client, "AAPL", "150.00")
    assert client.post("/api/v1/portfolio/sell", json={"symbol": "AAPL", "quantity": "4"}, headers=headers).status_code == 201
    data = client.get("/api/v1/portfolio", headers=headers).json()
    assert Decimal(data["realized_profit_loss"]) == Decimal("200.00")
    assert Decimal(data["unrealized_profit_loss"]) == Decimal("300.00")
    assert Decimal(data["total_profit_loss"]) == Decimal("500.00")
    assert Decimal(client.get("/api/v1/portfolio/holdings", headers=headers).json()[0]["quantity"]) == Decimal("6.000000")
    from app.core.config import settings
    settings.market_cache_seconds = 60


def test_full_profitable_sale_keeps_realized_profit_loss(client):
    headers = register_and_login(client)
    assert client.post("/api/v1/portfolio/buy", json={"symbol": "AAPL", "quantity": "10"}, headers=headers).status_code == 201
    set_price(client, "AAPL", "150.00")
    assert client.post("/api/v1/portfolio/sell", json={"symbol": "AAPL", "quantity": "10"}, headers=headers).status_code == 201
    data = client.get("/api/v1/portfolio", headers=headers).json()
    assert Decimal(data["realized_profit_loss"]) == Decimal("500.00")
    assert Decimal(data["unrealized_profit_loss"]) == Decimal("0.00")
    assert Decimal(data["total_profit_loss"]) == Decimal("500.00")
    from app.core.config import settings
    settings.market_cache_seconds = 60


def test_full_losing_sale_tracks_negative_realized_profit_loss(client):
    headers = register_and_login(client)
    assert client.post("/api/v1/portfolio/buy", json={"symbol": "AAPL", "quantity": "10"}, headers=headers).status_code == 201
    set_price(client, "AAPL", "80.00")
    assert client.post("/api/v1/portfolio/sell", json={"symbol": "AAPL", "quantity": "10"}, headers=headers).status_code == 201
    data = client.get("/api/v1/portfolio", headers=headers).json()
    assert Decimal(data["realized_profit_loss"]) == Decimal("-200.00")
    assert Decimal(data["total_profit_loss"]) == Decimal("-200.00")
    from app.core.config import settings
    settings.market_cache_seconds = 60

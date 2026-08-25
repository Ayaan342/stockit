import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# These are set before importing application modules. Tests never use .env or PostgreSQL.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-only-secret-not-for-production"
os.environ["INITIAL_VIRTUAL_CASH"] = "1000.00"
os.environ["MARKET_DATA_API_KEY"] = "test-market-key"

from app.api.deps import get_db
from app.database import Base
from app.main import app
from app.schemas.stock import StockHistoryPoint
from app.services.market_data import MarketDataProvider


class FakeMarketProvider(MarketDataProvider):
    def __init__(self) -> None:
        self.prices = {"AAPL": Decimal("100.00"), "MSFT": Decimal("200.00")}
        self.quote_calls = 0

    async def search(self, query: str) -> list[dict]:
        return [
            {"symbol": symbol, "name": f"{symbol} Inc.", "exchange": "NASDAQ"}
            for symbol in self.prices
            if query.upper() in symbol
        ]

    async def quote(self, symbol: str) -> Decimal:
        self.quote_calls += 1
        return self.prices[symbol.upper()]

    async def details(self, symbol: str) -> dict:
        normalized = symbol.upper()
        if normalized not in self.prices:
            raise KeyError(normalized)
        return {"symbol": normalized, "name": f"{normalized} Inc.", "exchange": "NASDAQ"}

    async def history(self, symbol: str) -> list[StockHistoryPoint]:
        price = await self.quote(symbol)
        now = datetime.now(timezone.utc)
        return [
            StockHistoryPoint(timestamp=now - timedelta(days=1), close=price),
            StockHistoryPoint(timestamp=now, close=price),
        ]


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    from app.services.market_data import MarketDataService

    app.state.market_service = MarketDataService(FakeMarketProvider())
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def register_and_login(client, email: str = "user@example.com") -> dict[str, str]:
    response = client.post("/api/v1/auth/register", json={"name": "Test User", "email": email, "password": "secure-pass-123"})
    assert response.status_code == 201, response.text
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "secure-pass-123"})
    assert token.status_code == 200, token.text
    return {"Authorization": f"Bearer {token.json()['access_token']}"}

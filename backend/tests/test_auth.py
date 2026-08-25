from tests.conftest import register_and_login


def test_register_login_and_current_user(client):
    headers = register_and_login(client)
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"


def test_duplicate_registration_and_unauthenticated_access(client):
    register_and_login(client)
    duplicate = client.post("/api/v1/auth/register", json={"name": "Other", "email": "user@example.com", "password": "secure-pass-123"})
    assert duplicate.status_code == 409
    assert client.get("/api/v1/auth/me").status_code == 401


def test_registration_creates_a_virtual_portfolio(client):
    headers = register_and_login(client)
    portfolio = client.get("/api/v1/portfolio", headers=headers)
    assert portfolio.status_code == 200
    assert portfolio.json()["cash_balance"] == "1000.00"

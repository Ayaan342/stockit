# StockIt backend

FastAPI, SQLAlchemy, PostgreSQL, and Alembic backend for StockIt's virtual portfolio platform.

## Setup

Use Python 3.12+ and create a virtual environment outside version control.

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set real local values in `.env`; never commit it. Required variables are `DATABASE_URL` and `JWT_SECRET`. `MARKET_DATA_API_KEY` is needed for live stock search, prices, and history.

## Database migrations

Create the PostgreSQL database/user first, then apply migrations without dropping or recreating anything:

```powershell
cd backend
alembic upgrade head
```

The original users migration is retained. The second migration adds user profile/cash fields and StockIt tables additively.

## Run

```powershell
cd backend
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for Swagger UI.

## Tests

```powershell
cd backend
pytest
```

Tests use a temporary SQLite database and a fake market-data provider. They never connect to `DATABASE_URL` from your `.env` and do not modify PostgreSQL.

## API

- `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`
- `GET /api/v1/stocks`, `GET /api/v1/stocks/search?q=`, `GET /api/v1/stocks/{symbol}`, `GET /api/v1/stocks/{symbol}/history`
- Watchlist CRUD and add/remove stock endpoints under `/api/v1/watchlists`
- Portfolio summary, holdings, transactions, performance, buy, and sell endpoints under `/api/v1/portfolio`

All watchlist and portfolio endpoints require `Authorization: Bearer <JWT>`.

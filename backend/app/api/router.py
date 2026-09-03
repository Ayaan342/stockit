from fastapi import APIRouter

from app.api.routes import auth, portfolio, stocks, watchlists

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(stocks.router)
api_router.include_router(watchlists.router)
api_router.include_router(portfolio.router)

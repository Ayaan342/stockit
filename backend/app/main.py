from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.services.market_data import MarketDataService, TwelveDataProvider

app = FastAPI(title="StockIt API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.state.market_service = MarketDataService(TwelveDataProvider())
app.include_router(api_router)


@app.get("/")
def root():
    return {"message": "StockIt API is running"}


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok"}

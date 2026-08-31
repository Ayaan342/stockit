import logging
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.services.market_data import MarketDataService, TwelveDataProvider, YahooFinanceProvider

app = FastAPI(title="StockIt API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.state.market_service = MarketDataService(TwelveDataProvider(), YahooFinanceProvider())
app.include_router(api_router)

logger = logging.getLogger("uvicorn.error")
_TIMED_PATHS = frozenset({
    "/api/v1/portfolio",
    "/api/v1/portfolio/holdings",
    "/api/v1/portfolio/transactions",
    "/api/v1/watchlists",
    "/health",
})


@app.middleware("http")
async def log_request_timing(request: Request, call_next):
    """Emit one wall-clock measurement for the endpoints used on Overview."""
    if request.url.path not in _TIMED_PATHS:
        return await call_next(request)
    started = perf_counter()
    request.state.timings = {"middleware_entered": 0.0}
    logger.info("request_timing stage=middleware_entered path=%s", request.url.path)
    response = await call_next(request)
    response_ready_ms = (perf_counter() - started) * 1000
    request.state.timings["response_ready"] = response_ready_ms
    logger.info("request_timing stage=response_ready path=%s elapsed_ms=%.1f", request.url.path, response_ready_ms)
    total_ms = (perf_counter() - started) * 1000
    timing_values = request.state.timings
    server_timing = [f"{name};dur={duration:.1f}" for name, duration in timing_values.items()]
    server_timing.append(f"total;dur={total_ms:.1f}")
    response.headers["Server-Timing"] = ", ".join(server_timing)
    logger.info(
        "request_timing path=%s status=%s elapsed_ms=%.1f",
        request.url.path,
        response.status_code,
        total_ms,
    )
    return response


@app.get("/")
def root():
    return {"message": "StockIt API is running"}


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok"}

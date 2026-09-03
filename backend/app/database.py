import os
import logging
from time import perf_counter

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be configured before starting the application")

engine = create_engine(DATABASE_URL)
logger = logging.getLogger("uvicorn.error")


@event.listens_for(engine, "checkout")
def log_pool_checkout(dbapi_connection, connection_record, connection_proxy) -> None:
    connection_record.info["stockit_checked_out_at"] = perf_counter()
    logger.info(
        "db_pool event=checkout checked_out=%s size=%s overflow=%s",
        engine.pool.checkedout(), engine.pool.size(), engine.pool.overflow(),
    )


@event.listens_for(engine, "checkin")
def log_pool_checkin(dbapi_connection, connection_record) -> None:
    checked_out_at = connection_record.info.pop("stockit_checked_out_at", None)
    request = connection_record.info.pop("stockit_timing_request", None)
    held_ms = (perf_counter() - checked_out_at) * 1000 if checked_out_at is not None else 0.0
    logger.info(
        "db_pool event=checkin held_ms=%.1f checked_out=%s size=%s overflow=%s",
        held_ms, engine.pool.checkedout(), engine.pool.size(), engine.pool.overflow(),
    )
    if request is not None and hasattr(request.state, "timings"):
        request.state.timings["connection_held"] = held_ms

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass

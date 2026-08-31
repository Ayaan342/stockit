from collections.abc import Generator
import logging
from time import perf_counter

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import event
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import SessionLocal
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)
logger = logging.getLogger("uvicorn.error")


@event.listens_for(Session, "after_begin")
def record_connection_checkout(session: Session, transaction, connection) -> None:
    """Separate initial pool wait from the auth/query measurement."""
    started = session.info.pop("connection_checkout_started", None)
    request = session.info.get("timing_request")
    if started is None or request is None:
        return
    elapsed_ms = (perf_counter() - started) * 1000
    connection.info["stockit_timing_request"] = request
    logger.info("db_timing stage=connection_checkout elapsed_ms=%.1f", elapsed_ms)
    if hasattr(request.state, "timings"):
        request.state.timings["connection_checkout"] = elapsed_ms


def get_db(request: Request) -> Generator[Session, None, None]:
    started = perf_counter()
    if hasattr(request.state, "timings"):
        request.state.timings["dependency_start"] = 0.0
    logger.info("db_timing stage=dependency_start")
    db = SessionLocal()
    db.info["timing_request"] = request
    # Session construction is lazy: the first query below is where a database
    # connection is actually checked out. Keeping this separate makes that
    # distinction clear in request timing logs.
    elapsed_ms = (perf_counter() - started) * 1000
    logger.info("db_timing stage=session_create elapsed_ms=%.1f", elapsed_ms)
    if hasattr(request.state, "timings"):
        request.state.timings["session"] = elapsed_ms
    try:
        yield db
    except Exception:
        rollback_started = perf_counter()
        db.rollback()
        logger.info("db_timing stage=dependency_error_rollback elapsed_ms=%.1f", (perf_counter() - rollback_started) * 1000)
        raise
    finally:
        cleanup_started = perf_counter()
        logger.info("db_timing stage=dependency_cleanup_start")
        if db.in_transaction():
            rollback_started = perf_counter()
            db.rollback()
            rollback_elapsed = (perf_counter() - rollback_started) * 1000
            logger.info("db_timing stage=dependency_rollback elapsed_ms=%.1f", rollback_elapsed)
            if hasattr(request.state, "timings"):
                request.state.timings["dependency_rollback"] = rollback_elapsed
        close_started = perf_counter()
        db.close()
        close_elapsed = (perf_counter() - close_started) * 1000
        cleanup_elapsed = (perf_counter() - cleanup_started) * 1000
        logger.info("db_timing stage=dependency_close elapsed_ms=%.1f", close_elapsed)
        logger.info("db_timing stage=dependency_cleanup_total elapsed_ms=%.1f", cleanup_elapsed)
        if hasattr(request.state, "timings"):
            request.state.timings["dependency_close"] = close_elapsed
            request.state.timings["dependency_cleanup"] = cleanup_elapsed


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired credentials")
    if credentials is None:
        raise error
    try:
        subject = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise error from exc
    query_started = perf_counter()
    # Session construction is lazy. The first authenticated lookup is where a
    # pool checkout may wait, and the event above records that portion.
    db.info["connection_checkout_started"] = query_started
    user = db.get(User, int(subject)) if subject.isdigit() else None
    elapsed_ms = (perf_counter() - query_started) * 1000
    logger.info("auth_timing stage=current_user_db elapsed_ms=%.1f", elapsed_ms)
    if hasattr(request.state, "timings"):
        request.state.timings["auth_db"] = elapsed_ms
    if user is None:
        raise error
    return user

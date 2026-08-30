from collections.abc import Generator
import logging
from time import perf_counter

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import SessionLocal
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)
logger = logging.getLogger("uvicorn.error")


def get_db(request: Request) -> Generator[Session, None, None]:
    started = perf_counter()
    db = SessionLocal()
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
        db.rollback()
        raise
    finally:
        db.close()


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
    user = db.get(User, int(subject)) if subject.isdigit() else None
    elapsed_ms = (perf_counter() - query_started) * 1000
    logger.info("auth_timing stage=current_user_db elapsed_ms=%.1f", elapsed_ms)
    if hasattr(request.state, "timings"):
        request.state.timings["auth_db"] = elapsed_ms
    if user is None:
        raise error
    return user

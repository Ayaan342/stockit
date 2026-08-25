import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_requires_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(APP_ENV="production", JWT_SECRET="")


def test_development_does_not_invent_a_jwt_secret():
    settings = Settings(APP_ENV="development", JWT_SECRET="")
    assert settings.jwt_secret == ""

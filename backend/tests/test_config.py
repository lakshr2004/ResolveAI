
import pytest
from pydantic import ValidationError

from app.config import Settings


def valid_settings(**overrides):
    settings = {
        "jwt_secret_key": "a" * 40,
        "jwt_algorithm": "HS256",
        "access_token_expire_minutes": 30,
        "max_upload_mb": 10,
        "max_request_body_mb": 12,
    }

    settings.update(overrides)

    return Settings(**settings)


def test_valid_security_configuration():
    settings = valid_settings()

    assert settings.max_upload_mb == 10
    assert settings.max_request_body_mb == 12


@pytest.mark.parametrize(
    "value",
    [0, -1],
)
def test_reject_invalid_upload_limit(value):
    with pytest.raises(ValidationError):
        valid_settings(max_upload_mb=value)


@pytest.mark.parametrize(
    "value",
    [0, -1],
)
def test_reject_invalid_request_body_limit(value):
    with pytest.raises(ValidationError):
        valid_settings(max_request_body_mb=value)


def test_reject_request_limit_not_greater_than_upload_limit():
    with pytest.raises(ValidationError):
        valid_settings(
            max_upload_mb=10,
            max_request_body_mb=10,
        )


def test_reject_short_jwt_secret():
    with pytest.raises(ValidationError):
        valid_settings(jwt_secret_key="short-secret")


def test_reject_unsupported_jwt_algorithm():
    with pytest.raises(ValidationError):
        valid_settings(jwt_algorithm="HS512")


def test_reject_invalid_token_expiry():
    with pytest.raises(ValidationError):
        valid_settings(access_token_expire_minutes=0)

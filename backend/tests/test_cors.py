import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import Settings


def test_cors_allowed_origin_response():
    client = TestClient(app)
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_untrusted_origin_rejected():
    client = TestClient(app)
    response = client.get(
        "/health",
        headers={"Origin": "http://malicious-site.com"}
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_cors_options_preflight_allowed():
    client = TestClient(app)
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization, Content-Type",
        }
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "GET" in response.headers.get("access-control-allow-methods", "")
    assert "Authorization" in response.headers.get("access-control-allow-headers", "")


def test_cors_options_preflight_untrusted_rejected():
    client = TestClient(app)
    response = client.options(
        "/health",
        headers={
            "Origin": "http://untrusted-origin.com",
            "Access-Control-Request-Method": "GET",
        }
    )
    assert response.status_code in (200, 400, 405)
    assert "access-control-allow-origin" not in response.headers


def test_cors_authorization_and_content_type_headers_permitted():
    client = TestClient(app)
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization, Content-Type, Accept",
        }
    )
    assert response.status_code == 200
    allowed_headers = response.headers.get("access-control-allow-headers", "")
    assert "Authorization" in allowed_headers
    assert "Content-Type" in allowed_headers
    assert "Accept" in allowed_headers


def test_cors_methods_supported():
    client = TestClient(app)
    for method in ["GET", "POST", "PATCH", "DELETE"]:
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": method,
            }
        )
        assert response.status_code == 200
        assert method in response.headers.get("access-control-allow-methods", "")


def test_settings_rejects_wildcard_origin():
    with pytest.raises(ValueError, match="Wildcard CORS origin"):
        Settings(cors_origins="*")


def test_settings_rejects_empty_origin():
    with pytest.raises(ValueError, match="CORS_ORIGINS cannot be empty"):
        Settings(cors_origins="")
    with pytest.raises(ValueError, match="CORS_ORIGINS must contain at least one valid origin"):
        Settings(cors_origins="   ,   ")


def test_settings_rejects_malformed_origin():
    with pytest.raises(ValueError, match="Invalid CORS origin"):
        Settings(cors_origins="not-a-url")
    with pytest.raises(ValueError, match="Cannot contain paths"):
        Settings(cors_origins="http://localhost:5173/path")


def test_multiple_explicit_origins_parsing():
    s = Settings(cors_origins="http://localhost:5173, https://resolve-ai-dun.vercel.app")
    origins = [o.strip() for o in s.cors_origins.split(",") if o.strip()]
    assert len(origins) == 2
    assert "http://localhost:5173" in origins
    assert "https://resolve-ai-dun.vercel.app" in origins


def test_allow_credentials_is_false():
    client = TestClient(app)
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"}
    )
    assert response.headers.get("access-control-allow-credentials") != "true"

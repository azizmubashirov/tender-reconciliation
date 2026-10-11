import asyncio

import pytest
from fastapi.testclient import TestClient

from app.core import health
from app.core.config import Settings
from app.main import app

client = TestClient(app)


async def ok() -> None:
    return None


async def refused() -> None:
    raise ConnectionError("connection refused")


async def not_configured() -> None:
    raise health.CheckSkippedError("R2 credentials are not set in .env")


async def hangs() -> None:
    await asyncio.sleep(10)


def test_liveness() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "CHECKS", {"postgres": ok, "redis": ok})

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert {c["status"] for c in body["components"].values()} == {"ok"}


def test_readiness_fails_when_a_component_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "CHECKS", {"postgres": ok, "redis": refused})

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["components"]["postgres"]["status"] == "ok"
    assert body["components"]["redis"]["status"] == "error"
    assert "ConnectionError" in body["components"]["redis"]["detail"]


def test_skipped_component_does_not_fail_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "CHECKS", {"postgres": ok, "object_storage": not_configured})

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json()["components"]["object_storage"]["status"] == "skipped"


def test_hanging_component_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "CHECKS", {"redis": hangs})
    monkeypatch.setattr(health, "CHECK_TIMEOUT_S", 0.05)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["components"]["redis"]["detail"] == "TimeoutError"


@pytest.mark.parametrize(
    ("env", "expected"),
    [("local", "skipped"), ("pilot", "error")],
)
def test_missing_r2_credentials(monkeypatch: pytest.MonkeyPatch, env: str, expected: str) -> None:
    settings = Settings(env=env, s3_endpoint_url=None, _env_file=None)
    monkeypatch.setattr(health, "get_settings", lambda: settings)
    monkeypatch.setattr(health, "CHECKS", {"object_storage": health.check_object_storage})

    response = client.get("/api/v1/health/ready")

    assert response.json()["components"]["object_storage"]["status"] == expected


def test_empty_env_values_mean_unset() -> None:
    settings = Settings(anthropic_api_key="", cf_account_id="", _env_file=None)

    assert settings.anthropic_api_key is None
    assert settings.llm_base_url is None

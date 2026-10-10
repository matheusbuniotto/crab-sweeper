"""The webhook gate: reject forgeries, ignore noise, never crash."""

import hashlib
import hmac
import json

from httpx import ASGITransport, AsyncClient

from crabsweeper.app import app
from crabsweeper.config import Provider, Settings

SECRET = "secret"


def _settings() -> Settings:
    return Settings(
        app_id="1",
        private_key="key",
        webhook_secret=SECRET,
        provider=Provider("", "", ""),
        mention="@crabsweeper",
        port=8000,
    )


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


async def test_health_reports_configuration() -> None:
    app.state.settings = _settings()
    async with _client() as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_a_bad_signature_is_rejected() -> None:
    app.state.settings = _settings()
    headers = {"x-github-event": "ping", "x-hub-signature-256": "sha256=bad"}
    async with _client() as client:
        response = await client.post("/webhook", content=b"{}", headers=headers)
    assert response.status_code == 401


async def test_a_valid_but_irrelevant_event_is_ignored() -> None:
    app.state.settings = _settings()
    body = json.dumps({"action": "created"}).encode()
    headers = {"x-github-event": "ping", "x-hub-signature-256": _sign(body)}
    async with _client() as client:
        response = await client.post("/webhook", content=body, headers=headers)
    assert response.status_code == 200
    assert response.text == "ignored"

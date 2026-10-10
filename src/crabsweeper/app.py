"""The webhook server: verify, resolve, dispatch. Work happens in `review`."""

from __future__ import annotations

import logging
import os

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse

from crabsweeper.config import Settings, settings_from_env
from crabsweeper.events import parse_review_request
from crabsweeper.github import GitHub
from crabsweeper.models import ReviewRequest
from crabsweeper.review import run_review
from crabsweeper.signature import verify

logger = logging.getLogger("crabsweeper")

settings = settings_from_env(os.environ)
app = FastAPI(title="CrabSweeper")
app.state.settings = settings


@app.get("/health")
async def health(request: Request) -> dict[str, str]:
    current: Settings = request.app.state.settings
    return {
        "status": "ok",
        "github": "configured" if current.github_configured else "unconfigured",
        "provider": "configured" if current.provider.configured else "unconfigured",
    }


@app.post("/webhook")
async def webhook(
    request: Request,
    background: BackgroundTasks,
    x_github_event: str = Header(default=""),
    x_hub_signature_256: str | None = Header(default=None),
) -> PlainTextResponse:
    body = await request.body()
    current: Settings = request.app.state.settings
    if not verify(current.webhook_secret, body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="bad signature")
    payload = await request.json()
    review_request = parse_review_request(x_github_event, payload, mention=current.mention)
    if review_request is None:
        return PlainTextResponse("ignored")
    background.add_task(_review, current, review_request)
    return PlainTextResponse("accepted")


async def _review(current: Settings, request: ReviewRequest) -> None:
    github = GitHub(app_id=current.app_id, private_key=current.private_key)
    try:
        await run_review(current, github, request)
    except Exception as exc:  # noqa: BLE001 — a webhook must never crash the server
        logger.error("review failed: %s", type(exc).__name__)  # noqa: TRY400
    finally:
        await github.aclose()

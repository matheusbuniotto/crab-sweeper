"""Turn a review request into a posted review. The two halves meet here."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol

from crabsweeper import ai as ai_module
from crabsweeper.checks import run_checks
from crabsweeper.config import Provider, Settings
from crabsweeper.models import AiReview, Check, PullRequest, Review, ReviewRequest
from crabsweeper.render import labels_for, render, render_in_progress

logger = logging.getLogger("crabsweeper")

Reviewer = Callable[[Provider, PullRequest, Sequence[Check]], Awaitable[AiReview]]


class GitHubLike(Protocol):
    async def pull(self, installation_id: int, repo: str, number: int) -> PullRequest: ...

    async def upsert_comment(
        self, installation_id: int, repo: str, number: int, body: str
    ) -> str: ...

    async def add_labels(
        self, installation_id: int, repo: str, number: int, labels: Sequence[str]
    ) -> None: ...


async def run_review(
    settings: Settings,
    github: GitHubLike,
    request: ReviewRequest,
    *,
    reviewer: Reviewer = ai_module.review,
) -> str:
    """Read the PR, run both halves, and post one updated comment plus labels."""
    await github.upsert_comment(
        request.installation_id,
        request.repo,
        request.number,
        render_in_progress(request),
    )
    pull = await github.pull(request.installation_id, request.repo, request.number)
    checks = run_checks(pull)
    ai = await _ai(settings, pull, checks, reviewer)
    review = Review(request=request, pull=pull, checks=checks, ai=ai)
    body = render(review)
    comment_id = await github.upsert_comment(
        request.installation_id, request.repo, request.number, body
    )
    await github.add_labels(
        request.installation_id, request.repo, request.number, labels_for(review)
    )
    return comment_id


async def _ai(
    settings: Settings,
    pull: PullRequest,
    checks: Sequence[Check],
    reviewer: Reviewer,
) -> AiReview:
    if not settings.provider.configured:
        return unavailable()
    try:
        return await reviewer(settings.provider, pull, checks)
    except Exception as exc:  # noqa: BLE001 — a failed AI half must not sink the review
        logger.warning("ai review failed: %s", type(exc).__name__)
        return unavailable()


def unavailable() -> AiReview:
    return AiReview(
        summary="Deterministic checks only; no model is configured.",
        kind="Change",
        worth_it=True,
        readiness="AI review unavailable.",
        findings=(),
        before_merge=(),
        labels=(),
    )

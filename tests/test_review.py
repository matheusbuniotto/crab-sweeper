"""The two halves meet in `run_review`, which posts exactly one comment."""

from collections.abc import Sequence

from crabsweeper.config import Provider, Settings
from crabsweeper.models import AiReview, PullRequest, ReviewRequest
from crabsweeper.render import MARKER
from crabsweeper.review import run_review


def _pull() -> PullRequest:
    return PullRequest(
        repo="acme/widgets",
        number=1,
        title="title",
        body="Closes #5",
        author="ada",
        draft=False,
        mergeable=True,
        files=(),
    )


def _request() -> ReviewRequest:
    return ReviewRequest(
        installation_id=1,
        repo="acme/widgets",
        number=1,
        head_sha="abc123",
        action="opened",
    )


def _settings(*, configured: bool) -> Settings:
    return Settings(
        app_id="1",
        private_key="key",
        webhook_secret="secret",
        provider=Provider("https://gateway.example/v1", "api-key" if configured else "", "model"),
        mention="@crabsweeper",
        port=8000,
    )


class _FakeGitHub:
    def __init__(self, pull: PullRequest) -> None:
        self._pull = pull
        self.comments: list[str] = []
        self.labels: list[tuple[str, ...]] = []

    async def pull(self, installation_id: int, repo: str, number: int) -> PullRequest:
        return self._pull

    async def upsert_comment(self, installation_id: int, repo: str, number: int, body: str) -> str:
        self.comments.append(body)
        return "1"

    async def add_labels(
        self, installation_id: int, repo: str, number: int, labels: Sequence[str]
    ) -> None:
        self.labels.append(tuple(labels))


def _ai() -> AiReview:
    return AiReview(
        summary="summary",
        kind="Fix",
        worth_it=True,
        readiness="ready",
        findings=(),
        before_merge=(),
        labels=("P2",),
    )


async def test_a_review_posts_one_comment_and_applies_labels() -> None:
    github = _FakeGitHub(_pull())

    async def reviewer(provider: Provider, pull: PullRequest, checks: object) -> AiReview:
        return _ai()

    comment_id = await run_review(_settings(configured=True), github, _request(), reviewer=reviewer)
    assert comment_id == "1"
    assert len(github.comments) == 1
    assert MARKER in github.comments[0]
    assert github.labels == [("P2",)]


async def test_an_unconfigured_provider_skips_the_model_but_still_posts() -> None:
    github = _FakeGitHub(_pull())

    async def reviewer(provider: Provider, pull: PullRequest, checks: object) -> AiReview:
        raise AssertionError("the reviewer must not run without a provider")

    await run_review(_settings(configured=False), github, _request(), reviewer=reviewer)
    assert "no model is configured" in github.comments[0]


async def test_a_failing_model_degrades_instead_of_raising() -> None:
    github = _FakeGitHub(_pull())

    async def reviewer(provider: Provider, pull: PullRequest, checks: object) -> AiReview:
        raise RuntimeError("boom")

    await run_review(_settings(configured=True), github, _request(), reviewer=reviewer)
    assert "AI review unavailable" in github.comments[0]

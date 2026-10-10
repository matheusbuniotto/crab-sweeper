"""The review comment mirrors the maintainer format."""

from crabsweeper.models import AiReview, Check, Finding, PullRequest, Review, ReviewRequest
from crabsweeper.render import MARKER, labels_for, render, verdict


def _review(
    *,
    checks: tuple[Check, ...] = (),
    findings: tuple[Finding, ...] = (),
    before_merge: tuple[str, ...] = (),
    labels: tuple[str, ...] = ("P2",),
    suggestion: str | None = None,
) -> Review:
    ai = AiReview(
        summary="Separates durable results from notifications.",
        kind="Refactor",
        worth_it=True,
        readiness="Clear value, one routing defect remains.",
        findings=findings,
        before_merge=before_merge,
        labels=labels,
        suggestion=suggestion,
    )
    pull = PullRequest(
        repo="acme/widgets",
        number=7,
        title="title",
        body="Closes #1",
        author="ada",
        draft=False,
        mergeable=True,
        files=(),
    )
    request = ReviewRequest(
        installation_id=1,
        repo="acme/widgets",
        number=7,
        head_sha="abc123",
        action="opened",
    )
    return Review(request=request, pull=pull, checks=checks, ai=ai)


def test_a_blocking_check_requests_changes() -> None:
    review = _review(checks=(Check("secrets", False, "Possible secrets", blocking=True),))
    assert verdict(review) == "changes requested"
    text = render(review)
    assert MARKER in text
    assert "- [ ] secrets: Possible secrets" in text


def test_a_severe_finding_requests_changes() -> None:
    review = _review(findings=(Finding("P1", "Thread leak", "detail", "src/a.py", 288),))
    assert verdict(review) == "changes requested"
    assert "`src/a.py:288`" in render(review)


def test_a_clean_review_looks_ready() -> None:
    review = _review(checks=(Check("diff-size", True, "3 files, 10 changed lines"),))
    assert verdict(review) == "looks ready"
    assert "Nothing blocking." in render(review)


def test_the_suggested_fix_is_rendered() -> None:
    review = _review(suggestion="```suggestion\nx = 1\n```")
    assert "## Suggested fix" in render(review)


def test_the_status_label_is_derived_from_the_verdict() -> None:
    model_said = _review(labels=("P2", "status: needs-fix"), findings=(Finding("P2", "x", "y"),))
    assert labels_for(model_said) == ("P2", "status: ready")
    blocked = _review(labels=("status: ready",), checks=(Check("secrets", False, "s", True),))
    assert labels_for(blocked) == ("status: needs-fix",)

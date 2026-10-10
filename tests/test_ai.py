"""The model reply parses into a review, or degrades gracefully."""

import json

from crabsweeper.ai import choose_model, parse_review
from crabsweeper.config import Provider, Route
from crabsweeper.models import FileChange, PullRequest


def _pull(changed: int) -> PullRequest:
    return PullRequest(
        repo="acme/widgets",
        number=1,
        title="title",
        body="",
        author="ada",
        draft=False,
        mergeable=True,
        files=(FileChange("a.py", changed, 0, ""),),
    )


def test_the_model_is_chosen_by_diff_size() -> None:
    provider = Provider("https://x/v1", "key", "fallback", route=Route("cheap", "strong", 10))
    assert choose_model(provider, _pull(5)) == "cheap"
    assert choose_model(provider, _pull(50)) == "strong"


def test_an_unset_route_falls_back_to_the_default_model() -> None:
    assert choose_model(Provider("https://x/v1", "key", "fallback"), _pull(500)) == "fallback"


def test_the_reported_cost_is_kept() -> None:
    content = json.dumps({"summary": "s", "findings": []})
    review = parse_review(content, model="cheap", cost_usd=0.0021)
    assert review.model == "cheap"
    assert review.cost_usd == 0.0021


def test_a_structured_reply_becomes_a_review() -> None:
    content = json.dumps(
        {
            "summary": "Separates results from notifications.",
            "kind": "Refactor",
            "worth_it": True,
            "readiness": "One routing defect.",
            "findings": [
                {
                    "priority": "P1",
                    "title": "Thread leak",
                    "detail": "detail",
                    "file": "src/a.py",
                    "line": 288,
                }
            ],
            "before_merge": ["Fix the route"],
            "labels": ["P2"],
            "suggestion": "```suggestion\nx = 1\n```",
        }
    )
    review = parse_review(content)
    assert review.kind == "Refactor"
    assert review.findings[0].priority == "P1"
    assert review.findings[0].file == "src/a.py"
    assert review.findings[0].line == 288
    assert review.before_merge == ("Fix the route",)
    assert review.labels == ("P2",)
    assert review.suggestion


def test_a_fenced_reply_is_unwrapped() -> None:
    content = "```json\n" + json.dumps({"summary": "s", "findings": []}) + "\n```"
    assert parse_review(content).summary == "s"


def test_a_garbage_reply_degrades_to_a_summary() -> None:
    review = parse_review("the model rambled")
    assert review.findings == ()
    assert review.summary == "the model rambled"

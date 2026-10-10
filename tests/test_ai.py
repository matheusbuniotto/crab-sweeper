"""The model reply parses into a review, or degrades gracefully."""

import json

from crabsweeper.ai import parse_review


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

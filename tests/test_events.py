"""Webhook payloads resolve to review requests, or nothing."""

from typing import Any

from crabsweeper.events import parse_review_request
from crabsweeper.models import ReviewRequest

MENTION = "@crabsweeper"


def _pull_payload(action: str = "opened") -> dict[str, Any]:
    return {
        "action": action,
        "installation": {"id": 7},
        "repository": {"full_name": "acme/widgets"},
        "pull_request": {"number": 42, "head": {"sha": "abc123"}},
    }


def _comment_payload(body: str, *, pull: bool = True) -> dict[str, Any]:
    issue: dict[str, Any] = {"number": 42}
    if pull:
        issue["pull_request"] = {"url": "https://api.github.com/pulls/42"}
    return {
        "action": "created",
        "installation": {"id": 7},
        "repository": {"full_name": "acme/widgets"},
        "issue": issue,
        "comment": {"body": body},
    }


def test_an_opened_pull_request_becomes_a_request() -> None:
    request = parse_review_request("pull_request", _pull_payload(), mention=MENTION)
    assert request == ReviewRequest(
        installation_id=7,
        repo="acme/widgets",
        number=42,
        head_sha="abc123",
        action="opened",
    )


def test_a_synchronize_event_also_triggers() -> None:
    assert parse_review_request("pull_request", _pull_payload("synchronize"), mention=MENTION)


def test_non_trigger_actions_are_ignored() -> None:
    assert parse_review_request("pull_request", _pull_payload("closed"), mention=MENTION) is None


def test_a_mention_on_a_pull_request_comment_becomes_a_request() -> None:
    payload = _comment_payload("hey @crabsweeper re-review please")
    request = parse_review_request("issue_comment", payload, mention=MENTION)
    assert request is not None
    assert (request.repo, request.number) == ("acme/widgets", 42)


def test_a_comment_without_the_mention_is_ignored() -> None:
    payload = _comment_payload("just chatting")
    assert parse_review_request("issue_comment", payload, mention=MENTION) is None


def test_a_mention_on_a_plain_issue_is_ignored() -> None:
    payload = _comment_payload("@crabsweeper", pull=False)
    assert parse_review_request("issue_comment", payload, mention=MENTION) is None


def test_other_events_are_ignored() -> None:
    assert parse_review_request("push", {"action": "created"}, mention=MENTION) is None

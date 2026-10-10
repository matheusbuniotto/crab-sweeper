"""Webhook payloads to review requests. Pure parsing; no network."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from crabsweeper.models import ReviewRequest

TRIGGER_ACTIONS = frozenset({"opened", "synchronize", "ready_for_review", "reopened"})


def parse_review_request(
    event: str,
    payload: Mapping[str, Any],
    *,
    mention: str,
) -> ReviewRequest | None:
    """Resolve a webhook to a review request, or `None` when it is not ours."""
    if event == "pull_request":
        return _from_pull_request(payload)
    if event == "issue_comment":
        return _from_issue_comment(payload, mention)
    return None


def _from_pull_request(payload: Mapping[str, Any]) -> ReviewRequest | None:
    if payload.get("action") not in TRIGGER_ACTIONS:
        return None
    pull = payload.get("pull_request") or {}
    return _request(payload, int(pull["number"]), _head_sha(payload))


def _from_issue_comment(payload: Mapping[str, Any], mention: str) -> ReviewRequest | None:
    if payload.get("action") != "created":
        return None
    issue = payload.get("issue") or {}
    if "pull_request" not in issue:
        return None
    body = (payload.get("comment") or {}).get("body") or ""
    if mention.lower() not in body.lower():
        return None
    return _request(payload, int(issue["number"]), "")


def _head_sha(payload: Mapping[str, Any]) -> str:
    head = (payload.get("pull_request") or {}).get("head") or {}
    return str(head.get("sha") or "")


def _request(payload: Mapping[str, Any], number: int, head_sha: str) -> ReviewRequest:
    return ReviewRequest(
        installation_id=int((payload.get("installation") or {})["id"]),
        repo=str((payload.get("repository") or {})["full_name"]),
        number=number,
        head_sha=head_sha,
        action=str(payload.get("action") or ""),
    )

"""AI review over any OpenAI-compatible chat endpoint. Network lives here only."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from crabsweeper.config import Provider
from crabsweeper.models import AiReview, Check, Finding, PullRequest

TIMEOUT_SECONDS = 90.0
MAX_DIFF_CHARS = 24000

SYSTEM_PROMPT = """You are CrabSweeper, a concise senior code reviewer.
Review the pull request for correctness, scope, and merge risk.
Return ONLY a JSON object with this shape:
{
  "summary": "one or two sentences on what this changes",
  "kind": "Feature | Fix | Refactor | Docs | Chore",
  "worth_it": true,
  "readiness": "one sentence verdict",
  "findings": [
    {"priority": "P0|P1|P2|P3", "title": "...", "detail": "...", "file": null, "line": 0}
  ],
  "before_merge": ["short action items"],
  "labels": ["P2", "merge-risk: ...", "status: ..."],
  "suggestion": "a fenced ```suggestion block for a simple mechanical fix, or null"
}
Rules: only report real issues you can point at; do not invent file paths; only add a
suggestion when the fix is simple and mechanical; keep every string short."""


async def review(provider: Provider, pull: PullRequest, checks: Sequence[Check]) -> AiReview:
    model = choose_model(provider, pull)
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt(pull, checks)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
        "max_tokens": provider.budget.max_output_tokens,
    }
    if provider.max_price:
        payload["provider"] = {"max_price": {"request": provider.budget.max_usd}}
    if provider.reasoning_effort:
        payload["reasoning"] = {"effort": provider.reasoning_effort}
    headers = {"Authorization": f"Bearer {provider.api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(base_url=provider.base_url, timeout=TIMEOUT_SECONDS) as client:
        response = await client.post("/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    choice = (data.get("choices") or [{}])[0]
    content = (choice.get("message") or {}).get("content")
    return parse_review(
        content if isinstance(content, str) else "",
        model=model,
        cost_usd=_cost(data),
    )


def choose_model(provider: Provider, pull: PullRequest) -> str:
    """Small diffs go to the cheap/free model; large ones to the stronger model."""
    return provider.route.choose(pull.changed_lines, provider.model)


def user_prompt(pull: PullRequest, checks: Sequence[Check]) -> str:
    lines = [
        f"# Pull request\n{pull.repo}#{pull.number}: {pull.title}",
        f"Author: {pull.author}",
        f"Body:\n{pull.body or '(empty)'}",
        "# Deterministic checks",
        "\n".join(
            f"- {check.name}: {'pass' if check.ok else 'fail'} — {check.detail}" for check in checks
        ),
        "# Diff",
        _diff(pull),
    ]
    return "\n\n".join(lines)


def parse_review(content: str, *, model: str = "", cost_usd: float | None = None) -> AiReview:
    """Parse the model's JSON. A malformed reply degrades to a summary-only review."""
    try:
        data = json.loads(_strip_fence(content))
    except (ValueError, TypeError):
        return _fallback(content, model, cost_usd)
    if not isinstance(data, dict):
        return _fallback(content, model, cost_usd)
    return AiReview(
        summary=str(data.get("summary") or ""),
        kind=str(data.get("kind") or "Change"),
        worth_it=bool(data.get("worth_it", True)),
        readiness=str(data.get("readiness") or ""),
        findings=tuple(_finding(item) for item in _items(data.get("findings"))),
        before_merge=tuple(str(item) for item in _items(data.get("before_merge"))),
        labels=tuple(str(item) for item in _items(data.get("labels"))),
        suggestion=data.get("suggestion") or None,
        model=model,
        cost_usd=cost_usd,
    )


def _cost(data: object) -> float | None:
    usage = data.get("usage") if isinstance(data, Mapping) else None
    value = usage.get("cost") if isinstance(usage, Mapping) else None
    return float(value) if isinstance(value, (int, float)) else None


def _diff(pull: PullRequest) -> str:
    chunks = [
        f"## {change.filename} (+{change.additions}/-{change.deletions})\n{change.patch}"
        for change in pull.files
    ]
    text = "\n\n".join(chunks)
    if len(text) > MAX_DIFF_CHARS:
        return text[:MAX_DIFF_CHARS] + "\n\n[diff truncated]"
    return text


def _strip_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
    return text.strip()


def _items(value: object) -> Sequence[Any]:
    return value if isinstance(value, list) else ()


def _finding(item: object) -> Finding:
    data: Mapping[str, Any] = item if isinstance(item, dict) else {}
    line = data.get("line")
    return Finding(
        priority=str(data.get("priority") or "P3"),
        title=str(data.get("title") or ""),
        detail=str(data.get("detail") or ""),
        file=data.get("file") or None,
        line=line if isinstance(line, int) else None,
    )


def _fallback(content: str, model: str, cost_usd: float | None) -> AiReview:
    summary = content.strip()[:280] or (
        "The model returned no output — it likely spent the token budget on reasoning."
    )
    return AiReview(
        summary=summary,
        kind="Change",
        worth_it=True,
        readiness="AI review could not be parsed.",
        findings=(),
        before_merge=(),
        labels=(),
        model=model,
        cost_usd=cost_usd,
    )

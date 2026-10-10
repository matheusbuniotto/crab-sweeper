"""Render the review comment. Pure string building."""

from __future__ import annotations

from crabsweeper.models import AiReview, Check, Finding, Review

MARKER = "<!-- crabsweeper-review -->"
SEVERE = frozenset({"P0", "P1"})


def render(review: Review) -> str:
    lines = [
        MARKER,
        f"## CrabSweeper review: {verdict(review)}",
        "",
        review.ai.summary,
        "",
        *_scores(review),
        "",
        *_product(review.ai),
        "",
        *_before_merge(review),
        "",
        *_findings(review.ai),
        "",
        *_checks(review.checks),
    ]
    if review.ai.suggestion:
        lines += ["", "## Suggested fix", "", review.ai.suggestion]
    lines += ["", _footer(review)]
    return "\n".join(lines).rstrip() + "\n"


def _footer(review: Review) -> str:
    parts = [f"_Reviewed head `{review.request.head_sha or 'unknown'}`"]
    if review.ai.model:
        parts.append(f"model `{review.ai.model}`")
    if review.ai.cost_usd is not None:
        parts.append(f"cost ${review.ai.cost_usd:.4f}")
    return " · ".join(parts) + "._"


def verdict(review: Review) -> str:
    return "changes requested" if _blocked(review) else "looks ready"


def _blocked(review: Review) -> bool:
    failed = any(check.blocking and not check.ok for check in review.checks)
    severe = any(finding.priority in SEVERE for finding in review.ai.findings)
    return failed or severe


def _scores(review: Review) -> list[str]:
    passed = sum(1 for check in review.checks if check.ok)
    total = len(review.checks)
    meaning = "Blocking items remain." if _blocked(review) else "No blockers detected."
    return [
        "## Review scores",
        "",
        "| Measure | Result | What it means |",
        "|---|---|---|",
        f"| **Deterministic checks** | {passed}/{total} passed | Diff heuristics. |",
        f"| **AI findings** | {len(review.ai.findings)} | Model review of intent. |",
        f"| **Merge readiness** | {verdict(review)} | {meaning} |",
    ]


def _product(ai: AiReview) -> list[str]:
    worth = "Yes" if ai.worth_it else "No"
    return ["## Product", "", f"**Kind:** {ai.kind} · **Worth it:** {worth}", "", ai.readiness]


def _before_merge(review: Review) -> list[str]:
    items = list(review.ai.before_merge)
    items += [
        f"{check.name}: {check.detail}"
        for check in review.checks
        if check.blocking and not check.ok
    ]
    if not items:
        return ["## Before merge", "", "Nothing blocking."]
    return ["## Before merge", "", *(f"- [ ] {item}" for item in items)]


def _findings(ai: AiReview) -> list[str]:
    if not ai.findings:
        return ["## Findings", "", "No findings."]
    lines = ["## Findings", ""]
    for finding in ai.findings:
        lines.append(f"- **[{finding.priority}]** {finding.title}{_where(finding)}")
        lines.append(f"  {finding.detail}")
    return lines


def _where(finding: Finding) -> str:
    if finding.file and finding.line:
        return f" — `{finding.file}:{finding.line}`"
    if finding.file:
        return f" — `{finding.file}`"
    return ""


def _checks(checks: tuple[Check, ...]) -> list[str]:
    lines = ["## Checks", "", "| Check | Result | Detail |", "|---|---|---|"]
    for check in checks:
        lines.append(f"| {check.name} | {_mark(check)} | {check.detail} |")
    return lines


def _mark(check: Check) -> str:
    if check.ok:
        return "pass"
    return "fail" if check.blocking else "warn"

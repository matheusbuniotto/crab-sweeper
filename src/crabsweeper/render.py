"""Render the review comment. Pure string building matching maintainer review format."""

from __future__ import annotations

from crabsweeper.models import AiReview, Check, FileChange, Finding, Review

MARKER = "<!-- crabsweeper-review -->"
SEVERE = frozenset({"P0", "P1"})

CRAB_RANKS: dict[int, tuple[str, str, str]] = {
    6: ("🦀 challenger crab", "S", "Exceptional readiness"),
    5: ("🦞 diamond lobster", "A", "Very strong readiness"),
    4: ("🐚 platinum hermit", "B", "Good normal PR; ordinary maintainer review"),
    3: ("🦐 gold shrimp", "C", "Useful, but confidence is limited"),
    2: ("🦪 silver shellfish", "D", "Proof or implementation needs work"),
    1: ("🧂 unranked krab", "F", "Not merge-ready"),
}


def render(review: Review) -> str:
    head_sha = review.request.head_sha or "unknown"
    sha_short = head_sha[:12] if len(head_sha) >= 12 else head_sha
    headline = (
        "changes requested before merge"
        if _blocked(review)
        else "needs maintainer review before merge"
    )

    lines = [
        MARKER,
        f"CrabSweeper review: {headline}. _Reviewed head `{sha_short}`._",
        "",
        "# CrabSweeper review",
        "",
        "## What this changes",
        "",
        review.ai.summary,
        "",
        *_merge_readiness(review, sha_short),
        "",
        *_scores(review),
        "",
        *_verification(review),
        "",
        *_how_it_fits(review),
        "",
        *_before_merge(review),
    ]

    if review.ai.findings:
        lines += ["", *_findings(review.ai)]

    if review.ai.suggestion:
        lines += ["", "## Suggested fix", "", review.ai.suggestion]

    lines += ["", *_agent_details(review)]
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


def labels_for(review: Review) -> tuple[str, ...]:
    """The model's labels, with any `status:` replaced by one derived from the verdict."""
    kept = [label for label in review.ai.labels if not label.strip().lower().startswith("status:")]
    status = "status: needs-fix" if _blocked(review) else "status: ready"
    return (*kept, status)


def _blocked(review: Review) -> bool:
    failed = any(check.blocking and not check.ok for check in review.checks)
    severe = any(finding.priority in SEVERE for finding in review.ai.findings)
    return failed or severe


def _priority(review: Review) -> str:
    for p in ("P0", "P1", "P2", "P3"):
        if any(f.priority == p for f in review.ai.findings):
            return p
    for label in review.ai.labels:
        upper = label.strip().upper()
        if upper in ("P0", "P1", "P2", "P3"):
            return upper
    return "P2"


def _merge_readiness(review: Review, sha_short: str) -> list[str]:
    blocked = _blocked(review)
    icon = "🛑" if blocked else "✅"
    title = "Changes requested" if blocked else "Ready for maintainer review"
    priority = _priority(review)

    text = review.ai.readiness or ("Blocking items remain." if blocked else "Ready to merge.")

    return [
        "## Merge readiness",
        "",
        f"{icon} **{title}**",
        "",
        text,
        "",
        f"**Priority:** {priority}",
        f"**Reviewed head:** `{sha_short}`",
    ]


def _format_rank(score: int | None) -> str:
    if score is None or score not in CRAB_RANKS:
        return "🌊 off-meta tidepool"
    name = CRAB_RANKS[score][0]
    return f"{name} **({score}/6)**"


def _rank_score(review: Review) -> int:
    if _blocked(review):
        return 1
    if review.ai.rank_score is not None:
        return max(1, min(6, review.ai.rank_score))
    if any(f.priority == "P2" for f in review.ai.findings):
        return 3
    if any(f.priority == "P3" for f in review.ai.findings):
        return 4
    return 4


def _scores(review: Review) -> list[str]:
    score = _rank_score(review)
    overall = _format_rank(score)
    overall_desc = (
        "Blocking items remain."
        if _blocked(review)
        else "A focused change has credible coverage and no blocking defect."
    )

    passed = sum(1 for c in review.checks if c.ok)
    total = len(review.checks)
    proof_rank = _format_rank(6 if passed == total else (3 if passed > 0 else 1))
    proof_desc = f"Deterministic diff heuristics: {passed}/{total} passed."

    patch_score = 1 if _blocked(review) else (3 if review.ai.findings else 4)
    patch_rank = _format_rank(patch_score)
    patch_desc = (
        f"{len(review.ai.findings)} review findings reported."
        if review.ai.findings
        else "No actionable review findings were identified."
    )

    return [
        "## Review scores",
        "",
        "| Measure | Result | What it means |",
        "|---|---|---|",
        f"| **Overall readiness** | {overall} | {overall_desc} |",
        f"| **Proof confidence** | {proof_rank} | {proof_desc} |",
        f"| **Patch quality** | {patch_rank} | {patch_desc} |",
    ]


def _verification(review: Review) -> list[str]:
    passed = sum(1 for c in review.checks if c.ok)
    total = len(review.checks)
    checks_str = f"{passed}/{total} passed"
    check_details = ", ".join(f"{c.name} ({_mark(c)})" for c in review.checks) or "None."

    file_count = len(review.pull.files)
    changed_lines = review.pull.changed_lines
    evidence_items = [f"{c.name}: {c.detail}" for c in review.checks if c.ok]
    evidence_str = (
        "<br>".join(evidence_items) if evidence_items else f"{file_count} files reviewed."
    )

    findings_result = "None" if not review.ai.findings else f"{len(review.ai.findings)} items"
    findings_evidence = (
        "No findings."
        if not review.ai.findings
        else "; ".join(f"{f.priority}: {f.title}" for f in review.ai.findings[:3])
    )

    secrets_check = next((c for c in review.checks if c.name == "secrets"), None)
    if secrets_check and not secrets_check.ok:
        sec_result = "Warning"
        sec_evidence = secrets_check.detail
    else:
        sec_result = "None"
        sec_evidence = "No credential-looking additions."

    return [
        "## Verification",
        "",
        "| Check | Result | Evidence |",
        "|---|---|---|",
        f"| **Deterministic checks** | {checks_str} | {check_details} |",
        f"| **Evidence reviewed** | {file_count} files, {changed_lines} lines | {evidence_str} |",
        f"| **Findings** | {findings_result} | {findings_evidence} |",
        f"| **Security** | {sec_result} | {sec_evidence} |",
    ]


def _how_it_fits(review: Review) -> list[str]:
    lines = ["## How this fits together", ""]
    intro = (
        review.ai.technical_review
        or review.ai.readiness
        or review.ai.summary
        or "Code and test architecture."
    )
    lines.append(intro)
    lines.append("")
    diagram = review.ai.diagram
    if not diagram or "flowchart" not in diagram:
        diagram = _generate_diagram(review)
    lines += ["```mermaid", diagram, "```"]
    return lines


def _generate_diagram(review: Review) -> str:
    areas = {_classify_file(f.filename) for f in review.pull.files}
    if "Tests" in areas and "Source" in areas:
        return (
            "flowchart LR\n"
            "    A[Input / Event] --> B[Source Implementation]\n"
            "    B --> C[Behavior / Output]\n"
            "    D[Tests] --> B\n"
            "    D --> C"
        )
    return (
        "flowchart LR\n    A[Pull Request] --> B[CrabSweeper Checks]\n    B --> C[Verified Review]"
    )


def _before_merge(review: Review) -> list[str]:
    items = list(review.ai.before_merge)
    items += [
        f"{check.name}: {check.detail}"
        for check in review.checks
        if check.blocking and not check.ok
    ]
    if not items:
        return ["## Before merge", "", "None. Nothing blocking."]
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


def _mark(check: Check) -> str:
    if check.ok:
        return "pass"
    return "fail" if check.blocking else "warn"


def _classify_file(filename: str) -> str:
    lower = filename.lower()
    parts = lower.split("/")
    base = parts[-1]
    if any(p in ("tests", "test") for p in parts[:-1]) or "test" in base:
        return "Tests"
    if any(p in ("docs", "doc") for p in parts[:-1]) or lower.endswith((".md", ".rst", ".txt")):
        return "Docs"
    config_exts = (".toml", ".yaml", ".yml", ".json", ".lock", ".env", ".env.example")
    if lower.endswith(config_exts) or base in ("dockerfile", "makefile", ".gitignore"):
        return "Config"
    if lower.endswith(
        (".py", ".ts", ".js", ".tsx", ".jsx", ".rs", ".go", ".c", ".cpp", ".h", ".java", ".sh")
    ):
        return "Source"
    return "Other"


def _pr_surface(files: tuple[FileChange, ...]) -> list[str]:
    categories = ["Source", "Tests", "Docs", "Config", "Generated", "Other"]
    stats: dict[str, list[int]] = {c: [0, 0, 0] for c in categories}

    for f in files:
        cat = _classify_file(f.filename)
        stats[cat][0] += 1
        stats[cat][1] += f.additions
        stats[cat][2] += f.deletions

    tot_files = len(files)
    tot_add = sum(f.additions for f in files)
    tot_del = sum(f.deletions for f in files)
    tot_net = tot_add - tot_del
    tot_net_str = f"+{tot_net}" if tot_net > 0 else str(tot_net)

    primary_parts = []
    for cat in ("Source", "Tests"):
        if stats[cat][0] > 0:
            net = stats[cat][1] - stats[cat][2]
            net_str = f"+{net}" if net > 0 else str(net)
            primary_parts.append(f"{cat} {net_str}")
    summary_str = (
        f"{', '.join(primary_parts)}. Total {tot_net_str} across {tot_files} files."
        if primary_parts
        else f"Total {tot_net_str} across {tot_files} files."
    )

    lines = [
        summary_str,
        "",
        "<details>",
        "<summary>View PR surface stats</summary>",
        "",
        "| Area | Files | Added | Removed | Net |",
        "|---|---:|---:|---:|---:|",
    ]
    for cat in categories:
        cf, ca, cd = stats[cat]
        cnet = ca - cd
        cnet_str = f"+{cnet}" if cnet > 0 else str(cnet)
        lines.append(f"| {cat} | {cf} | {ca} | {cd} | {cnet_str} |")
    lines.append(
        f"| **Total** | **{tot_files}** | **{tot_add}** | **{tot_del}** | **{tot_net_str}** |"
    )
    lines.append("")
    lines.append("</details>")
    return lines


def _technical_review(review: Review) -> list[str]:
    lines = ["Best possible solution:", ""]
    if review.ai.technical_review:
        lines.append(review.ai.technical_review)
    else:
        lines.append(
            review.ai.readiness or "Maintain consistency and adhere to existing test patterns."
        )
    return lines


def _rating_scale_table() -> list[str]:
    return [
        "| Score | Internal tier | Crab rank | Meaning |",
        "|---:|:---:|---|---|",
        "| **6/6** | S | 🦀 challenger crab | Exceptional readiness |",
        "| **5/6** | A | 🦞 diamond lobster | Very strong readiness |",
        "| **4/6** | B | 🐚 platinum hermit | Good normal PR; ordinary maintainer review |",
        "| **3/6** | C | 🦐 gold shrimp | Useful, but confidence is limited |",
        "| **2/6** | D | 🦪 silver shellfish | Proof or implementation needs work |",
        "| **1/6** | F | 🧂 unranked krab | Not merge-ready |",
        "| N/A | NA | 🌊 off-meta tidepool | Rating does not apply |",
        "",
        "Overall follows the weaker of proof and patch quality.",
    ]


def _workflow_explanation() -> list[str]:
    return [
        "- CrabSweeper keeps one durable marker-backed review comment per issue or PR.",
        "- Re-runs edit this comment so the latest verdict, findings, and automation markers"
        " stay together instead of adding duplicate bot comments.",
        "- Comment `@crabsweeper re-review` on an open PR to request a fresh review.",
    ]


def _agent_details(review: Review) -> list[str]:
    lines = [
        "<details>",
        "<summary><strong>Agent review details</strong></summary>",
        "",
        "### Security",
        "",
    ]
    sec_finding = next(
        (
            f
            for f in review.ai.findings
            if "secret" in f.title.lower() or "security" in f.title.lower()
        ),
        None,
    )
    sec_check = next((c for c in review.checks if c.name == "secrets" and not c.ok), None)
    if sec_finding:
        lines.append(f"**[{sec_finding.priority}]** {sec_finding.title}: {sec_finding.detail}")
    elif sec_check:
        lines.append(f"**Warning:** {sec_check.detail}")
    else:
        lines.append("None.")

    lines += ["", "### PR surface", "", *_pr_surface(review.pull.files), ""]
    lines += ["### Technical review", "", *_technical_review(review), ""]
    lines += ["### Rating scale", "", *_rating_scale_table(), ""]
    lines += ["### Workflow", "", *_workflow_explanation(), ""]
    lines += ["</details>"]
    return lines

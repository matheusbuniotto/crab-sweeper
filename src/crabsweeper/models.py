"""Typed boundaries for a review. Pure data; no I/O."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReviewRequest:
    """A webhook resolved to a reviewable pull request."""

    installation_id: int
    repo: str
    number: int
    head_sha: str
    action: str


@dataclass(frozen=True, slots=True)
class FileChange:
    filename: str
    additions: int
    deletions: int
    patch: str = ""


@dataclass(frozen=True, slots=True)
class PullRequest:
    repo: str
    number: int
    title: str
    body: str
    author: str
    draft: bool
    mergeable: bool | None
    files: tuple[FileChange, ...]

    @property
    def additions(self) -> int:
        return sum(change.additions for change in self.files)

    @property
    def deletions(self) -> int:
        return sum(change.deletions for change in self.files)

    @property
    def changed_lines(self) -> int:
        return self.additions + self.deletions


@dataclass(frozen=True, slots=True)
class Check:
    """One deterministic result. `blocking` failures hold the merge."""

    name: str
    ok: bool
    detail: str
    blocking: bool = False


@dataclass(frozen=True, slots=True)
class Finding:
    priority: str
    title: str
    detail: str
    file: str | None = None
    line: int | None = None


@dataclass(frozen=True, slots=True)
class AiReview:
    summary: str
    kind: str
    worth_it: bool
    readiness: str
    findings: tuple[Finding, ...]
    before_merge: tuple[str, ...]
    labels: tuple[str, ...]
    suggestion: str | None = None
    diagram: str | None = None
    technical_review: str | None = None
    rank_score: int | None = None
    model: str = ""
    cost_usd: float | None = None


@dataclass(frozen=True, slots=True)
class Review:
    request: ReviewRequest
    pull: PullRequest
    checks: tuple[Check, ...]
    ai: AiReview

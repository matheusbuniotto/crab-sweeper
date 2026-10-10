"""Deterministic, repo-agnostic checks over a pull request. Pure functions."""

from __future__ import annotations

import re

from crabsweeper.models import Check, FileChange, PullRequest

MAX_FILES = 40
MAX_CHANGED_LINES = 800
_CODE_SUFFIXES = frozenset(
    {"py", "ts", "tsx", "js", "jsx", "go", "rs", "java", "rb", "kt", "cs", "php", "c", "cpp", "h"}
)
_TEST_HINTS = ("test_", "_test.", "/tests/", "/test/", ".test.", ".spec.")
_MARKERS = ("TODO", "FIXME", "XXX", "HACK")
_ISSUE_REF = re.compile(r"#\d+")
_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{8,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
)


def run_checks(pull: PullRequest) -> tuple[Check, ...]:
    return (
        _linked_issue(pull),
        _diff_size(pull),
        _tests_with_code(pull),
        _leftover_markers(pull),
        _secrets(pull),
        _mergeable(pull),
    )


def _linked_issue(pull: PullRequest) -> Check:
    ok = bool(_ISSUE_REF.search(pull.body))
    detail = "PR body references an issue." if ok else "No issue reference in the PR body."
    return Check(name="linked-issue", ok=ok, detail=detail)


def _diff_size(pull: PullRequest) -> Check:
    ok = len(pull.files) <= MAX_FILES and pull.changed_lines <= MAX_CHANGED_LINES
    detail = f"{len(pull.files)} files, {pull.changed_lines} changed lines"
    if not ok:
        detail += f" (over {MAX_FILES} files / {MAX_CHANGED_LINES} lines)"
    return Check(name="diff-size", ok=ok, detail=detail)


def _tests_with_code(pull: PullRequest) -> Check:
    if not any(_is_code(change.filename) for change in pull.files):
        return Check(name="tests-changed", ok=True, detail="No source files changed.")
    ok = any(_is_test(change.filename) for change in pull.files)
    detail = "Source and tests changed together." if ok else "Source changed with no test change."
    return Check(name="tests-changed", ok=ok, detail=detail)


def _leftover_markers(pull: PullRequest) -> Check:
    hits = [change.filename for change in pull.files if _added_text(change, _MARKERS)]
    ok = not hits
    detail = "No leftover markers." if ok else f"Markers added in: {', '.join(hits)}"
    return Check(name="leftover-markers", ok=ok, detail=detail)


def _secrets(pull: PullRequest) -> Check:
    hits = [change.filename for change in pull.files if _added_pattern(change)]
    ok = not hits
    detail = "No credential-looking additions." if ok else f"Possible secrets in: {', '.join(hits)}"
    return Check(name="secrets", ok=ok, detail=detail, blocking=True)


def _mergeable(pull: PullRequest) -> Check:
    ok = pull.mergeable is not False
    detail = "No merge conflict reported." if ok else "GitHub reports a merge conflict."
    return Check(name="mergeable", ok=ok, detail=detail, blocking=True)


def _is_code(filename: str) -> bool:
    return not _is_test(filename) and filename.rsplit(".", 1)[-1].lower() in _CODE_SUFFIXES


def _is_test(filename: str) -> bool:
    lowered = filename.lower()
    return any(hint in lowered for hint in _TEST_HINTS)


def _added_text(change: FileChange, needles: tuple[str, ...]) -> bool:
    return any(
        any(needle in _added(line) for needle in needles)
        for line in change.patch.splitlines()
        if _is_addition(line)
    )


def _added_pattern(change: FileChange) -> bool:
    return any(
        any(pattern.search(_added(line)) for pattern in _SECRET_PATTERNS)
        for line in change.patch.splitlines()
        if _is_addition(line)
    )


def _is_addition(line: str) -> bool:
    return line.startswith("+") and not line.startswith("+++")


def _added(line: str) -> str:
    return line[1:]

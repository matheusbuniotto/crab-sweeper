"""Deterministic checks read the diff, never the network."""

from crabsweeper.checks import run_checks
from crabsweeper.models import Check, FileChange, PullRequest


def _pull(**over: object) -> PullRequest:
    defaults: dict[str, object] = {
        "repo": "acme/widgets",
        "number": 1,
        "title": "title",
        "body": "Closes #5",
        "author": "ada",
        "draft": False,
        "mergeable": True,
        "files": (),
    }
    defaults.update(over)
    return PullRequest(**defaults)  # type: ignore[arg-type]


def _check(checks: tuple[Check, ...], name: str) -> Check:
    return next(check for check in checks if check.name == name)


def test_a_clean_pull_request_passes_every_check() -> None:
    files = (
        FileChange("src/app.py", 3, 1, "+x = 1\n"),
        FileChange("tests/test_app.py", 2, 0, "+def test_x():\n"),
    )
    assert all(check.ok for check in run_checks(_pull(files=files)))


def test_a_missing_issue_reference_warns_without_blocking() -> None:
    linked = _check(run_checks(_pull(body="no reference")), "linked-issue")
    assert linked.ok is False
    assert linked.blocking is False


def test_source_without_tests_warns() -> None:
    files = (FileChange("src/app.py", 1, 0, "+x = 1\n"),)
    assert _check(run_checks(_pull(files=files)), "tests-changed").ok is False


def test_added_secrets_block() -> None:
    files = (FileChange("src/app.py", 1, 0, '+api_key = "abcdef1234567890"\n'),)
    secret = _check(run_checks(_pull(files=files)), "secrets")
    assert secret.ok is False
    assert secret.blocking is True


def test_added_markers_warn() -> None:
    files = (FileChange("src/app.py", 1, 0, "+# TODO: fix this\n"),)
    assert _check(run_checks(_pull(files=files)), "leftover-markers").ok is False


def test_an_oversized_diff_fails() -> None:
    files = tuple(FileChange(f"src/f{index}.py", 100, 0, "") for index in range(10))
    assert _check(run_checks(_pull(files=files)), "diff-size").ok is False


def test_a_merge_conflict_blocks() -> None:
    mergeable = _check(run_checks(_pull(mergeable=False)), "mergeable")
    assert mergeable.ok is False
    assert mergeable.blocking is True

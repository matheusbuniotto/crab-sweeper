#!/usr/bin/env python
"""Dry-run a review: fetch a PR, run both halves, print the comment. Posts nothing.

Usage: uv run python scripts/dry_run.py <owner/repo> <number>
"""

from __future__ import annotations

import asyncio
import os
import sys

from crabsweeper.ai import review as ai_review
from crabsweeper.checks import run_checks
from crabsweeper.config import settings_from_env
from crabsweeper.github import GitHub
from crabsweeper.models import Review, ReviewRequest
from crabsweeper.render import render


async def main(repo: str, number: int) -> None:
    settings = settings_from_env(os.environ)
    github = GitHub(app_id=settings.app_id, private_key=settings.private_key)
    try:
        installation = await github.installation_id(repo)
        pull = await github.pull(installation, repo, number)
        checks = run_checks(pull)
        ai = await ai_review(settings.provider, pull, checks)
    finally:
        await github.aclose()
    request = ReviewRequest(
        installation_id=installation,
        repo=repo,
        number=number,
        head_sha="",
        action="dry-run",
    )
    print(render(Review(request=request, pull=pull, checks=checks, ai=ai)))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: dry_run.py <owner/repo> <number>")
    asyncio.run(main(sys.argv[1], int(sys.argv[2])))

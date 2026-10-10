"""GitHub REST client: app JWT, installation tokens, PR reads, comment upsert."""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from typing import Any

import httpx
import jwt

from crabsweeper.models import FileChange, PullRequest
from crabsweeper.render import MARKER

API = "https://api.github.com"
ACCEPT = "application/vnd.github+json"
JWT_TTL_SECONDS = 540
FILES_PER_PAGE = 100
LABEL_COLOR = "ededed"


class GitHub:
    """A thin async client. One instance may serve several installations."""

    def __init__(
        self,
        *,
        app_id: str,
        private_key: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._app_id = app_id
        self._private_key = private_key
        self._client = client or httpx.AsyncClient(base_url=API, timeout=30.0)
        self._tokens: dict[int, str] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def installation_id(self, repo: str) -> int:
        """The installation covering `repo`. For tools and dry runs; webhooks carry it."""
        response = await self._client.get(
            f"/repos/{repo}/installation",
            headers={"Authorization": f"Bearer {self._jwt()}", "Accept": ACCEPT},
        )
        response.raise_for_status()
        return int(response.json()["id"])

    async def pull(self, installation_id: int, repo: str, number: int) -> PullRequest:
        headers = await self._auth(installation_id)
        pull = await self._get(f"/repos/{repo}/pulls/{number}", headers)
        return PullRequest(
            repo=repo,
            number=number,
            title=str(pull.get("title") or ""),
            body=str(pull.get("body") or ""),
            author=str((pull.get("user") or {}).get("login") or ""),
            draft=bool(pull.get("draft")),
            mergeable=pull.get("mergeable"),
            files=await self._files(repo, number, headers),
        )

    async def upsert_comment(
        self,
        installation_id: int,
        repo: str,
        number: int,
        body: str,
    ) -> str:
        """Edit this PR's existing CrabSweeper comment, or create the first one."""
        headers = await self._auth(installation_id)
        existing = await self._find_comment(repo, number, headers)
        if existing is not None:
            response = await self._client.patch(
                f"/repos/{repo}/issues/comments/{existing}",
                headers=headers,
                json={"body": body},
            )
            response.raise_for_status()
            return str(existing)
        response = await self._client.post(
            f"/repos/{repo}/issues/{number}/comments",
            headers=headers,
            json={"body": body},
        )
        response.raise_for_status()
        return str(response.json()["id"])

    async def add_labels(
        self,
        installation_id: int,
        repo: str,
        number: int,
        labels: Sequence[str],
    ) -> None:
        if not labels:
            return
        headers = await self._auth(installation_id)
        await self._ensure_labels(repo, headers, labels)
        response = await self._client.post(
            f"/repos/{repo}/issues/{number}/labels",
            headers=headers,
            json={"labels": list(labels)},
        )
        response.raise_for_status()

    async def _files(
        self,
        repo: str,
        number: int,
        headers: Mapping[str, str],
    ) -> tuple[FileChange, ...]:
        changes: list[FileChange] = []
        page = 1
        while True:
            path = f"/repos/{repo}/pulls/{number}/files?per_page={FILES_PER_PAGE}&page={page}"
            batch = await self._get(path, headers)
            changes.extend(_file_change(item) for item in batch)
            if len(batch) < FILES_PER_PAGE:
                return tuple(changes)
            page += 1

    async def _find_comment(
        self,
        repo: str,
        number: int,
        headers: Mapping[str, str],
    ) -> int | None:
        comments = await self._get(f"/repos/{repo}/issues/{number}/comments?per_page=100", headers)
        for comment in comments:
            if MARKER in str(comment.get("body") or ""):
                return int(comment["id"])
        return None

    async def _ensure_labels(
        self,
        repo: str,
        headers: Mapping[str, str],
        labels: Sequence[str],
    ) -> None:
        existing = {
            str(item.get("name") or "")
            for item in await self._get(f"/repos/{repo}/labels?per_page=100", headers)
        }
        for label in labels:
            if label in existing:
                continue
            response = await self._client.post(
                f"/repos/{repo}/labels",
                headers=headers,
                json={"name": label, "color": LABEL_COLOR},
            )
            if response.status_code not in (201, 422):
                response.raise_for_status()

    async def _get(self, path: str, headers: Mapping[str, str]) -> Any:
        response = await self._client.get(path, headers=headers)
        response.raise_for_status()
        return response.json()

    async def _auth(self, installation_id: int) -> dict[str, str]:
        return {"Authorization": f"token {await self._token(installation_id)}", "Accept": ACCEPT}

    async def _token(self, installation_id: int) -> str:
        cached = self._tokens.get(installation_id)
        if cached:
            return cached
        response = await self._client.post(
            f"/app/installations/{installation_id}/access_tokens",
            headers={"Authorization": f"Bearer {self._jwt()}", "Accept": ACCEPT},
        )
        response.raise_for_status()
        token = str(response.json()["token"])
        self._tokens[installation_id] = token
        return token

    def _jwt(self) -> str:
        now = int(time.time())
        claims = {"iat": now - 60, "exp": now + JWT_TTL_SECONDS, "iss": self._app_id}
        return jwt.encode(claims, self._private_key, algorithm="RS256")


def _file_change(item: Mapping[str, Any]) -> FileChange:
    return FileChange(
        filename=str(item.get("filename") or ""),
        additions=int(item.get("additions") or 0),
        deletions=int(item.get("deletions") or 0),
        patch=str(item.get("patch") or ""),
    )

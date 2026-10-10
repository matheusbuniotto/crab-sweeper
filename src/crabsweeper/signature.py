"""Webhook signature verification. Pure; no secret ever leaves this module."""

from __future__ import annotations

import hashlib
import hmac

PREFIX = "sha256="


def verify(secret: str, body: bytes, header: str | None) -> bool:
    """True when `header` is GitHub's HMAC-SHA256 of `body` under `secret`."""
    if not secret or not header or not header.startswith(PREFIX):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"{PREFIX}{expected}", header)

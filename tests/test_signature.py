"""The webhook signature gate."""

import hashlib
import hmac

from crabsweeper.signature import verify

SECRET = "s3cret"
BODY = b'{"action":"opened"}'


def _header(body: bytes) -> str:
    digest = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_a_valid_signature_is_accepted() -> None:
    assert verify(SECRET, BODY, _header(BODY)) is True


def test_a_tampered_body_is_rejected() -> None:
    assert verify(SECRET, BODY + b" ", _header(BODY)) is False


def test_a_missing_or_malformed_header_is_rejected() -> None:
    assert verify(SECRET, BODY, None) is False
    assert verify(SECRET, BODY, "deadbeef") is False


def test_an_empty_secret_is_rejected() -> None:
    assert verify("", BODY, _header(BODY)) is False

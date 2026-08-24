from datetime import UTC, datetime, timedelta

import pyotp
import pytest

from crowdent.auth import (
    AuthenticationError,
    PasswordManager,
    Role,
    SessionSigner,
    role_allows,
    verify_totp,
)

NOW = datetime(2026, 8, 24, 10, 0, tzinfo=UTC)


def test_argon2_password_hashes_verify_without_exposing_password() -> None:
    manager = PasswordManager()
    encoded = manager.hash("correct horse battery staple")

    assert encoded.startswith("$argon2")
    assert "correct horse battery staple" not in encoded
    assert manager.verify(encoded, "correct horse battery staple") is True
    assert manager.verify(encoded, "wrong") is False


def test_totp_can_be_verified_at_a_deterministic_time() -> None:
    secret = "JBSWY3DPEHPK3PXP"
    code = pyotp.TOTP(secret).at(NOW)

    assert verify_totp(secret, code, at=NOW, valid_window=0) is True
    assert verify_totp(secret, "000000", at=NOW, valid_window=0) is False


def test_role_hierarchy_is_explicit() -> None:
    assert role_allows(Role.ADMIN, Role.SUPERVISOR) is True
    assert role_allows(Role.SUPERVISOR, Role.OPERATOR) is True
    assert role_allows(Role.AUDITOR, Role.OPERATOR) is False
    assert role_allows(Role.OPERATOR, Role.SUPERVISOR) is False


def test_signed_session_rejects_expired_tokens() -> None:
    signer = SessionSigner(secret="s" * 48)
    token = signer.create_session(
        subject="operator-1",
        role=Role.OPERATOR,
        now=NOW,
        ttl=timedelta(minutes=5),
    )

    principal = signer.verify_session(token, now=NOW + timedelta(minutes=1))
    assert principal.subject == "operator-1"
    assert principal.role is Role.OPERATOR

    with pytest.raises(AuthenticationError, match="expired"):
        signer.verify_session(token, now=NOW + timedelta(minutes=6))

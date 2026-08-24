"""Offline authentication primitives for field-research mode."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


class AuthenticationError(ValueError):
    pass


class Role(StrEnum):
    OPERATOR = "operator"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"
    AUDITOR = "auditor"


_ROLE_LEVEL = {
    Role.OPERATOR: 1,
    Role.SUPERVISOR: 2,
    Role.ADMIN: 3,
    Role.AUDITOR: 0,
}


def role_allows(actual: Role | str, required: Role | str) -> bool:
    actual_role = Role(actual)
    required_role = Role(required)
    if actual_role is Role.AUDITOR:
        return required_role is Role.AUDITOR
    if required_role is Role.AUDITOR:
        return actual_role in {Role.ADMIN, Role.AUDITOR}
    return _ROLE_LEVEL[actual_role] >= _ROLE_LEVEL[required_role]


class PasswordManager:
    def __init__(self) -> None:
        self._hasher = PasswordHasher()

    def hash(self, password: str) -> str:
        if len(password) < 12:
            raise ValueError("password must be at least 12 characters")
        return self._hasher.hash(password)

    def verify(self, encoded: str, password: str) -> bool:
        try:
            return self._hasher.verify(encoded, password)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return False

    def needs_rehash(self, encoded: str) -> bool:
        try:
            return self._hasher.check_needs_rehash(encoded)
        except InvalidHashError:
            return True


def verify_totp(
    secret: str,
    code: str,
    *,
    at: datetime | None = None,
    valid_window: int = 1,
) -> bool:
    timestamp = at or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("TOTP verification time must be timezone-aware")
    if not code.isdigit() or len(code) != 6:
        return False
    return bool(
        pyotp.TOTP(secret).verify(
            code,
            for_time=timestamp,
            valid_window=valid_window,
        )
    )


@dataclass(frozen=True, slots=True)
class Principal:
    subject: str
    role: Role
    issued_at: datetime
    expires_at: datetime


class SessionSigner:
    def __init__(self, *, secret: str, issuer: str = "crowdent-local") -> None:
        if len(secret) < 32:
            raise ValueError("session signing secret must be at least 32 characters")
        self._secret = secret
        self._issuer = issuer

    def create_session(
        self,
        *,
        subject: str,
        role: Role | str,
        now: datetime | None = None,
        ttl: timedelta = timedelta(hours=8),
    ) -> str:
        issued = now or datetime.now(UTC)
        _require_aware(issued)
        if ttl <= timedelta(0):
            raise ValueError("session ttl must be positive")
        expires = issued + ttl
        claims = {
            "sub": subject,
            "role": Role(role).value,
            "iss": self._issuer,
            "iat": int(issued.timestamp()),
            "nbf": int(issued.timestamp()),
            "exp": int(expires.timestamp()),
            "research_only": True,
        }
        return str(jwt.encode(claims, self._secret, algorithm="HS256"))

    def verify_session(
        self,
        token: str,
        *,
        now: datetime | None = None,
    ) -> Principal:
        current = now or datetime.now(UTC)
        _require_aware(current)
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                issuer=self._issuer,
                options={
                    "require": ["sub", "role", "iat", "nbf", "exp", "iss"],
                    "verify_exp": False,
                    "verify_nbf": False,
                    "verify_iat": False,
                },
            )
        except jwt.PyJWTError as error:
            raise AuthenticationError("invalid signed session") from error
        issued = datetime.fromtimestamp(int(claims["iat"]), tz=UTC)
        not_before = datetime.fromtimestamp(int(claims["nbf"]), tz=UTC)
        expires = datetime.fromtimestamp(int(claims["exp"]), tz=UTC)
        if current < not_before:
            raise AuthenticationError("session is not active yet")
        if current >= expires:
            raise AuthenticationError("session has expired")
        if claims.get("research_only") is not True:
            raise AuthenticationError("invalid session safety claim")
        try:
            role = Role(str(claims["role"]))
        except ValueError as error:
            raise AuthenticationError("unknown session role") from error
        return Principal(
            subject=str(claims["sub"]),
            role=role,
            issued_at=issued,
            expires_at=expires,
        )


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")


__all__ = [
    "AuthenticationError",
    "PasswordManager",
    "Principal",
    "Role",
    "SessionSigner",
    "role_allows",
    "verify_totp",
]

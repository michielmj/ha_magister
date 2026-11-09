"""Exceptions raised by the Magister API layer.

Messages never contain secrets (passwords, TOTP secrets, tokens, cookies, authCode).
"""

from __future__ import annotations

from typing import Final

AUTH_INVALID: Final = "invalid_auth"
AUTH_TOTP_REQUIRED: Final = "totp_required"
AUTH_INVALID_TOTP: Final = "invalid_totp"
AUTH_UNSUPPORTED_LOGIN: Final = "unsupported_login"


class MagisterError(Exception):
    """Base class for all errors raised by this package."""


class MagisterAuthError(MagisterError):
    """Login failed.

    ``code`` is one of ``invalid_auth``, ``totp_required``, ``invalid_totp`` or
    ``unsupported_login`` (school SSO, passkey-only or other flows we cannot drive).
    These errors are never retried automatically.
    """

    def __init__(self, code: str, message: str | None = None) -> None:
        """Create the error with a machine-readable ``code``."""
        super().__init__(message or code)
        self.code = code


class MagisterConnectionError(MagisterError):
    """The network failed, timed out, or the server returned a 5xx status."""


class MagisterApiError(MagisterError):
    """Magister answered, but not with something we can use."""

    def __init__(
        self,
        message: str,
        status: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        """Create the error with the HTTP ``status`` (if any)."""
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after

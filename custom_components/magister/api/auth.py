"""Authentication against Magister (OpenID Connect, replayed over plain HTTP).

Flow (see docs/reference/magister-auth-flow.md):

1. ``GET accounts.magister.net/connect/authorize`` -> redirects to
   ``/account/login?sessionId=...&returnUrl=...`` (sets the ``XSRF-TOKEN`` cookie).
2. The login page's JS bundle holds an ``authCode`` that must accompany every
   challenge request; it is scraped dynamically.
3. ``POST /challenges/current|username|password|soft-token``.
4. Follow the final ``redirectURL``; the access token is in the URL fragment.
5. Later renewals try ``prompt=none`` with the session cookies first.

Secrets (password, TOTP secret, tokens, cookies, authCode) are never logged, never
put in exception messages and never shown by ``repr()``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final, Literal
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlsplit

import aiohttp
import pyotp
from yarl import URL

from .errors import (
    AUTH_INVALID,
    AUTH_INVALID_TOTP,
    AUTH_TOTP_REQUIRED,
    AUTH_UNSUPPORTED_LOGIN,
    MagisterApiError,
    MagisterAuthError,
    MagisterConnectionError,
)
from .login_page import (
    DEFAULT_SCOPE,
    extract_auth_code,
    find_login_script_url,
    parse_login_url,
    parse_oidc_scope,
)
from .utils import normalize_host

_LOGGER = logging.getLogger(__name__)

ACCOUNTS_HOST: Final = "accounts.magister.net"
ACCOUNTS_URL: Final = f"https://{ACCOUNTS_HOST}"
TOKEN_MARGIN: Final = 60.0
REQUEST_TIMEOUT: Final = aiohttp.ClientTimeout(total=30)
MAX_REDIRECTS: Final = 10
MAX_CHALLENGE_STEPS: Final = 8
DEFAULT_EXPIRES_IN: Final = 3600
USER_AGENT: Final = "ha-magister/0.0.1 (+https://github.com/michielmj/ha_magister)"

TokenSource = Literal["cached", "silent", "login"]

_RESERVED_URI_CHARS: Final = ";/?:@&=+$,#"
_PCT_RUN_RE = re.compile(r"(?:%[0-9A-Fa-f]{2})+")

_WRONG_CREDENTIALS: Final = frozenset(
    {
        "InvalidUsername",
        "InvalidPassword",
        "InvalidUsernameOrPassword",
        "UserHasNoAccess",
        "NoUsername",
        "NoPassword",
        "UserBlocked",
        "UserExpired",
        "UserNotActivated",
        "UserLockedOut",
        "DeviceLockedOut",
        "UserHasNoChallenges",
    }
)
_WRONG_CODE: Final = frozenset(
    {"InvalidCode", "IncorrectToken", "TotpExpired", "NoCode"}
)
_UNSUPPORTED: Final = frozenset(
    {
        "NoRedirectUrl",
        "InvalidIdPSelected",
        "IdPDisabled",
        "SsoDisabled",
        "NoPasswordChallenge",
    }
)
_NEVER_RETRY: Final = frozenset(
    {AUTH_INVALID, AUTH_TOTP_REQUIRED, AUTH_INVALID_TOTP, AUTH_UNSUPPORTED_LOGIN}
)


class _AuthCodeRejectedError(Exception):
    """Internal: Magister rejected our authCode (stale cache)."""


@dataclass(frozen=True, slots=True)
class _Reply:
    status: int
    headers: Mapping[str, str]
    text: str
    xsrf: str | None


def _decode_uri(value: str) -> str:
    """Emulate JavaScript ``decodeURI`` (does not decode reserved characters)."""

    def repl(match: re.Match[str]) -> str:
        raw = bytes.fromhex(match.group(0).replace("%", ""))
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return match.group(0)
        return "".join(
            f"%{ord(char):02X}" if char in _RESERVED_URI_CHARS else char
            for char in text
        )

    return _PCT_RUN_RE.sub(repl, value)


class MagisterAuth:
    """Obtains and caches Magister access tokens for one account."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        username: str,
        password: str,
        totp_secret: str | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Create the auth helper.

        ``session`` should have its own cookie jar (the silent renew relies on the
        ``accounts.magister.net`` session cookies). ``host`` is the school host,
        e.g. ``school.magister.net``.
        """
        self._session = session
        self._host = normalize_host(host)
        self._username = username
        self._password = password
        self._totp_secret = totp_secret.replace(" ", "") if totp_secret else None
        self._clock = clock

        self._token: str | None = None
        self._expires_at = 0.0
        self._generation = 0
        self._lock = asyncio.Lock()
        self._has_session = False
        self._xsrf: str | None = None
        self._scope: str | None = None
        self._auth_code: tuple[str, str] | None = None
        self._failure: MagisterAuthError | None = None
        self.last_token_source: TokenSource | None = None
        self.last_silent_failure: str | None = None

    def __repr__(self) -> str:
        """Representation without any credentials."""
        return f"MagisterAuth(host={self._host!r})"

    @property
    def host(self) -> str:
        """The school host name."""
        return self._host

    def update_credentials(
        self, password: str, totp_secret: str | None = None, username: str | None = None
    ) -> None:
        """Replace credentials (reauth) and clear the remembered auth failure."""
        if username is not None:
            self._username = username
        self._password = password
        self._totp_secret = totp_secret.replace(" ", "") if totp_secret else None
        self._failure = None
        self._token = None
        self._has_session = False

    # ------------------------------------------------------------------ token

    def _cached_token(self) -> str | None:
        if self._token and self._clock() < self._expires_at - TOKEN_MARGIN:
            return self._token
        return None

    async def async_get_token(self, *, force_refresh: bool = False) -> str:
        """Return a valid access token.

        Uses the cache (60 s margin), then a silent renew, then a full login.
        ``force_refresh`` skips the cache (used after a 401). ``last_token_source``
        tells which path was taken.
        """
        if not force_refresh and (token := self._cached_token()):
            self.last_token_source = "cached"
            return token
        generation = self._generation
        async with self._lock:
            if self._failure is not None:
                raise self._failure
            token = self._cached_token()
            if token and (not force_refresh or self._generation != generation):
                self.last_token_source = "cached"
                return token
            return await self._renew()

    async def _renew(self) -> str:
        if self._has_session:
            result = await self._silent_renew()
            if result is not None:
                return self._store(result, "silent")
        try:
            result = await self._full_login()
        except MagisterAuthError as err:
            if err.code in _NEVER_RETRY:
                self._failure = err
            self._token = None
            raise
        self._has_session = True
        return self._store(result, "login")

    def _store(self, result: tuple[str, int], source: TokenSource) -> str:
        token, expires_in = result
        self._token = token
        self._expires_at = self._clock() + expires_in
        self._generation += 1
        self.last_token_source = source
        _LOGGER.debug("Obtained Magister token via %s (valid %ss)", source, expires_in)
        return token

    # ----------------------------------------------------------------- HTTP

    async def _http(
        self,
        method: str,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> _Reply:
        all_headers = {"User-Agent": USER_AGENT, **(headers or {})}
        try:
            async with self._session.request(
                method,
                url,
                json=json_body,
                headers=all_headers,
                allow_redirects=False,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                text = (
                    await resp.text() if resp.status < 300 or resp.status == 400 else ""
                )
                cookie = resp.cookies.get("XSRF-TOKEN")
                xsrf = cookie.value if cookie is not None else None
                reply = _Reply(
                    status=resp.status,
                    headers={k: v for k, v in resp.headers.items()},
                    text=text,
                    xsrf=xsrf,
                )
        except TimeoutError as err:
            raise MagisterConnectionError("Timeout talking to Magister") from err
        except aiohttp.ClientError as err:
            raise MagisterConnectionError(
                f"Connection to Magister failed ({type(err).__name__})"
            ) from err
        if reply.xsrf:
            self._xsrf = reply.xsrf
        if reply.status >= 500:
            raise MagisterConnectionError(f"Magister server error {reply.status}")
        if reply.status == 429:
            raise MagisterApiError("Magister rate limit hit", status=429)
        return reply

    def _csrf_headers(self) -> dict[str, str]:
        token = self._xsrf
        if token is None:
            jar = self._session.cookie_jar.filter_cookies(URL(ACCOUNTS_URL))
            morsel = jar.get("XSRF-TOKEN")
            token = morsel.value if morsel is not None else None
        return {"X-XSRF-TOKEN": token} if token else {}

    # ------------------------------------------------------------ OIDC bits

    @property
    def _redirect_uri(self) -> str:
        return f"https://{self._host}/oidc/redirect_callback.html"

    async def _get_scope(self) -> str:
        if self._scope is None:
            reply = await self._http("GET", f"https://{self._host}/oidc_config.js")
            if reply.status != 200:
                raise MagisterApiError(
                    "Could not read the school's OIDC settings", status=reply.status
                )
            self._scope = parse_oidc_scope(reply.text)
            if self._scope == DEFAULT_SCOPE:
                _LOGGER.debug("Using built-in OIDC scope")
        return self._scope

    async def _authorize_url(self, *, prompt_none: bool) -> str:
        params = {
            "client_id": f"M6-{self._host}",
            "redirect_uri": self._redirect_uri,
            "response_type": "id_token token",
            "scope": await self._get_scope(),
            "state": secrets.token_hex(16),
            "nonce": secrets.token_hex(16),
            "acr_values": f"tenant:{self._host}",
        }
        if prompt_none:
            params["prompt"] = "none"
        return f"{ACCOUNTS_URL}/connect/authorize?{urlencode(params, quote_via=quote)}"

    def _is_callback(self, url: str) -> bool:
        parts = urlsplit(url)
        return (
            parts.netloc == self._host and parts.path == "/oidc/redirect_callback.html"
        )

    async def _follow(self, url: str) -> str:
        """Follow redirects manually until a login page, the callback or elsewhere.

        Returns the URL at which following stopped.
        """
        for _ in range(MAX_REDIRECTS):
            if parse_login_url(url) is not None or self._is_callback(url):
                return url
            reply = await self._http("GET", url, headers=self._csrf_headers())
            location = reply.headers.get("Location")
            if reply.status not in (301, 302, 303, 307, 308) or not location:
                return url
            url = urljoin(url, location)
            if urlsplit(url).netloc not in (ACCOUNTS_HOST, self._host):
                return url
        raise MagisterApiError("Too many redirects during login")

    @staticmethod
    def _fragment(url: str) -> dict[str, str]:
        return {k: v[0] for k, v in parse_qs(urlsplit(url).fragment).items()}

    def _token_from_callback(self, url: str) -> tuple[str, int] | None:
        """Return ``(token, expires_in)`` from a callback URL, else ``None``."""
        if not self._is_callback(url):
            return None
        fragment = self._fragment(url)
        token = fragment.get("access_token")
        if not token:
            return None
        try:
            expires_in = int(fragment.get("expires_in", DEFAULT_EXPIRES_IN))
        except ValueError:
            expires_in = DEFAULT_EXPIRES_IN
        return token, expires_in

    # ----------------------------------------------------------- silent renew

    async def _silent_renew(self) -> tuple[str, int] | None:
        """Try ``prompt=none``; return ``None`` when a full login is needed."""
        self.last_silent_failure = None
        try:
            end = await self._follow(await self._authorize_url(prompt_none=True))
        except (MagisterConnectionError, MagisterApiError) as err:
            self.last_silent_failure = type(err).__name__
            _LOGGER.debug("Silent renew failed (%s)", self.last_silent_failure)
            return None
        result = self._token_from_callback(end)
        if result is None:
            error = self._fragment(end).get("error") if self._is_callback(end) else None
            self.last_silent_failure = error or "no_token"
            _LOGGER.debug("Silent renew gave no token (%s)", self.last_silent_failure)
        return result

    # --------------------------------------------------------------- full login

    async def _full_login(self) -> tuple[str, int]:
        try:
            return await self._login_once()
        except _AuthCodeRejectedError:
            _LOGGER.debug("authCode rejected, refreshing it and retrying once")
            self._auth_code = None
        try:
            return await self._login_once()
        except _AuthCodeRejectedError as err:
            raise MagisterApiError(
                "Magister rejected the login request code; the flow may have changed"
            ) from err

    async def _login_once(self) -> tuple[str, int]:
        end = await self._follow(await self._authorize_url(prompt_none=False))
        if (result := self._token_from_callback(end)) is not None:
            return result  # an existing session cookie was still valid
        login = parse_login_url(end)
        if login is None:
            self._raise_for_foreign_url(end)
            raise MagisterApiError("Magister did not redirect to the login page")
        session_id, return_url = login

        page = await self._http("GET", end, headers=self._csrf_headers())
        if page.status != 200:
            raise MagisterApiError("Could not load the login page", status=page.status)
        auth_code = await self._get_auth_code(page.text)

        base: dict[str, Any] = {
            "sessionId": session_id,
            "returnUrl": _decode_uri(return_url),
            "authCode": auth_code,
        }
        redirect = await self._run_challenges(base)
        return await self._finish(redirect)

    async def _get_auth_code(self, login_html: str) -> str:
        script_url = urljoin(f"{ACCOUNTS_URL}/", find_login_script_url(login_html))
        if self._auth_code is not None and self._auth_code[0] == script_url:
            return self._auth_code[1]
        if urlsplit(script_url).netloc != ACCOUNTS_HOST:
            raise MagisterApiError(
                "Login script is hosted outside accounts.magister.net"
            )
        reply = await self._http("GET", script_url)
        if reply.status != 200:
            raise MagisterApiError(
                "Could not load the login script", status=reply.status
            )
        code = extract_auth_code(reply.text)
        self._auth_code = (script_url, code)
        return code

    async def _challenge(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        reply = await self._http(
            "POST",
            f"{ACCOUNTS_URL}{path}",
            json_body=body,
            headers={**self._csrf_headers(), "Accept": "application/json"},
        )
        try:
            data = json.loads(reply.text)
        except ValueError as err:
            raise MagisterApiError(
                "Unexpected response from the login service", status=reply.status
            ) from err
        if reply.status not in (200, 400) or not isinstance(data, dict):
            raise MagisterApiError(
                "Unexpected response from the login service", status=reply.status
            )
        return data

    async def _run_challenges(self, base: dict[str, Any]) -> str:
        """Answer challenges until Magister hands out the final ``redirectURL``."""
        data = await self._challenge("/challenges/current", base)
        sent: set[str] = set()
        for _ in range(MAX_CHALLENGE_STEPS):
            if redirect := data.get("redirectURL"):
                return str(redirect)
            if error := data.get("error"):
                self._raise_for_error(str(error))
            action = data.get("action")
            if action in sent:
                if action == "soft-token":
                    raise MagisterAuthError(
                        AUTH_INVALID_TOTP, "The TOTP code was rejected"
                    )
                raise MagisterApiError(f"Unexpected repeated login step '{action}'")
            if action == "username":
                payload: dict[str, Any] = {
                    "action": "username",
                    "username": self._username,
                }
            elif action == "password":
                payload = {
                    "action": "password",
                    "password": self._password,
                    "userWantsToPairSoftToken": False,
                    "userSkippedFido": True,
                }
            elif action == "soft-token":
                if not self._totp_secret:
                    raise MagisterAuthError(
                        AUTH_TOTP_REQUIRED, "This account requires a TOTP code"
                    )
                payload = {"action": "soft-token", "code": self._totp_code()}
            else:
                raise MagisterAuthError(
                    AUTH_UNSUPPORTED_LOGIN,
                    f"Magister asked for an unsupported login step ({action})",
                )
            sent.add(str(action))
            _LOGGER.debug("Submitting login step %s", action)
            data = await self._challenge(f"/challenges/{action}", {**base, **payload})
        raise MagisterApiError(  # pragma: no cover - guarded by ``sent``
            "Login did not finish after too many steps"
        )

    def _totp_code(self) -> str:
        assert self._totp_secret is not None
        try:
            return pyotp.TOTP(self._totp_secret).now()
        except ValueError as err:  # binascii.Error: malformed base32 secret
            raise MagisterAuthError(
                AUTH_INVALID_TOTP, "The TOTP secret is not valid base32"
            ) from err

    @staticmethod
    def _raise_for_error(error: str) -> None:
        if error == "AuthCodeValidation":
            raise _AuthCodeRejectedError
        if error in _WRONG_CODE:
            raise MagisterAuthError(AUTH_INVALID_TOTP, f"TOTP code rejected ({error})")
        if error in _WRONG_CREDENTIALS:
            raise MagisterAuthError(AUTH_INVALID, f"Login rejected ({error})")
        if error in _UNSUPPORTED:
            raise MagisterAuthError(
                AUTH_UNSUPPORTED_LOGIN, f"Login method not supported ({error})"
            )
        raise MagisterApiError(f"Magister login error ({error})")

    def _raise_for_foreign_url(self, url: str) -> None:
        host = urlsplit(url).netloc
        if host and host not in (ACCOUNTS_HOST, self._host):
            raise MagisterAuthError(
                AUTH_UNSUPPORTED_LOGIN,
                "This school uses an external identity provider (SSO), "
                "which is not supported",
            )

    async def _finish(self, redirect: str) -> tuple[str, int]:
        url = urljoin(f"{ACCOUNTS_URL}/", redirect)
        self._raise_for_foreign_url(url)
        end = await self._follow(url)
        if (result := self._token_from_callback(end)) is not None:
            return result
        self._raise_for_foreign_url(end)
        error = self._fragment(end).get("error") if self._is_callback(end) else None
        raise MagisterApiError(
            f"Login finished without an access token ({error or 'no token'})"
        )

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
from collections.abc import Awaitable, Callable, Mapping
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
    MagisterError,
)
from .login_page import (
    DEFAULT_SCOPE,
    extract_auth_code,
    find_login_script_url,
    parse_login_url,
    parse_oidc_scope,
)
from .utils import normalize_host, parse_retry_after

_LOGGER = logging.getLogger(__name__)

ACCOUNTS_HOST: Final = "accounts.magister.net"
ACCOUNTS_URL: Final = f"https://{ACCOUNTS_HOST}"
TOKEN_MARGIN: Final = 60.0  # maximum; shortened for tokens living < 120 s
TOTP_PERIOD: Final = 30
CONNECTION_BACKOFF: Final = 30.0
CONNECTION_BACKOFF_MAX: Final = 300.0
POST_PASSWORD_BACKOFF: Final = 300.0
POST_PASSWORD_MAX_FAILURES: Final = 3
RETRY_AFTER_MAX: Final = 3600.0
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
        "InvalidChallenge",
        "InvalidChallengeValue",
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
        "TenantNotFound",
        "NoAllowedTenants",
        "TenantNotAllowed",
        "DisabledTenant",
        "NoTenantSelected",
        "InvalidTenantSelected",
        "NoSchoolSelected",
    }
)
_AUTH_CODE_ERRORS: Final = frozenset({"AuthCodeValidation", "AuthCodeValidationError"})


class _AuthCodeRejectedError(Exception):
    """Internal: Magister rejected our authCode (stale cache)."""


@dataclass(frozen=True, slots=True)
class _Reply:
    status: int
    headers: Mapping[str, str]
    text: str
    xsrf: str | None
    retry_after: float | None = None


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
        wall_clock: Callable[[], float] = time.time,
        max_password_submissions: int | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
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
        self._wall_clock = wall_clock
        self._max_password_submissions = max_password_submissions
        self._sleep = sleep

        self._token: str | None = None
        self._expires_at = 0.0
        self._generation = 0
        self._lock = asyncio.Lock()
        self._has_session = False
        self._xsrf: str | None = None
        self._scope: str | None = None
        self._auth_code: tuple[str, str] | None = None
        self._failure: MagisterError | None = None
        self._password_sent = False
        self._last_totp_step: int | None = None
        self._blocked_until = 0.0
        self._backoff = CONNECTION_BACKOFF
        self._post_password_failures = 0
        self._valid_until = 0.0
        self.last_token_source: TokenSource | None = None
        self.last_silent_failure: str | None = None
        self.password_submissions = 0

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
        self._blocked_until = 0.0
        self._backoff = CONNECTION_BACKOFF
        self._post_password_failures = 0
        self._token = None
        self._has_session = False

    # ------------------------------------------------------------------ token

    def _cached_token(self) -> str | None:
        if self._token and self._clock() < self._valid_until:
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
        if self._clock() < self._blocked_until:
            raise MagisterConnectionError("Waiting before retrying the login")
        self._password_sent = False
        try:
            result = await self._full_login()
        except MagisterAuthError as err:
            # Every MagisterAuthError code is final: never retried automatically.
            self._failure = err
            self._token = None
            raise
        except MagisterConnectionError as err:
            self._token = None
            if self._password_sent:
                # The password may or may not have been counted: back off for a
                # long time and give up after a few such failures in a row.
                self._post_password_failures += 1
                if self._post_password_failures >= POST_PASSWORD_MAX_FAILURES:
                    self._failure = err
                else:
                    self._blocked_until = self._clock() + POST_PASSWORD_BACKOFF
            else:
                # No usable answer: back off instead of hammering the login service.
                self._block_for(None)
            raise
        except MagisterError as err:
            # Once the password was sent, any other failure may count towards a
            # lockout, so it is remembered and never retried automatically.
            self._token = None
            if self._password_sent:
                self._failure = err
            else:
                retry_after = (
                    err.retry_after if isinstance(err, MagisterApiError) else None
                )
                self._block_for(retry_after)
            raise
        self._backoff = CONNECTION_BACKOFF
        self._post_password_failures = 0
        self._has_session = True
        return self._store(result, "login")

    def _block_for(self, retry_after: float | None) -> None:
        """Do not start a full login again before ``retry_after`` or the backoff."""
        if retry_after is not None:
            delay = min(retry_after, RETRY_AFTER_MAX)
        else:
            delay = self._backoff
            self._backoff = min(self._backoff * 2, CONNECTION_BACKOFF_MAX)
        self._blocked_until = self._clock() + delay

    def _store(self, result: tuple[str, int], source: TokenSource) -> str:
        token, expires_in = result
        self._token = token
        self._expires_at = self._clock() + expires_in
        self._valid_until = self._expires_at - min(TOKEN_MARGIN, expires_in / 2)
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
                xsrf = (
                    cookie.value
                    if cookie is not None and urlsplit(url).netloc == ACCOUNTS_HOST
                    else None
                )
                reply = _Reply(
                    status=resp.status,
                    headers={k: v for k, v in resp.headers.items()},
                    text=text,
                    xsrf=xsrf,
                    retry_after=parse_retry_after(resp.headers.get("Retry-After")),
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
            raise MagisterApiError(
                "Magister rate limit hit", status=429, retry_after=reply.retry_after
            )
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
            parts.scheme == "https"
            and parts.netloc == self._host
            and parts.path == "/oidc/redirect_callback.html"
        )

    async def _follow(self, url: str) -> str:
        """Follow redirects manually until a login page, the callback or elsewhere.

        Returns the URL at which following stopped.
        """
        for _ in range(MAX_REDIRECTS):
            if parse_login_url(url) is not None or self._is_callback(url):
                return url
            if urlsplit(url).scheme != "https":
                raise MagisterApiError("Refusing a non-HTTPS redirect")
            reply = await self._http("GET", url)
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

        page = await self._http("GET", end)
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
            # The browser strips ``action`` from the body; it is part of the URL.
            if action == "username":
                payload: dict[str, Any] = {"username": self._username}
            elif action == "password":
                limit = self._max_password_submissions
                if limit is not None and self.password_submissions >= limit:
                    raise MagisterAuthError(
                        AUTH_INVALID,
                        "Password submission limit reached for this run",
                        "PasswordLimitReached",
                    )
                payload = {
                    "password": self._password,
                    "userWantsToPairSoftToken": False,
                    "userSkippedFido": False,
                }
                self._password_sent = True
                self.password_submissions += 1
            elif action == "soft-token":
                if not self._totp_secret:
                    raise MagisterAuthError(
                        AUTH_TOTP_REQUIRED, "This account requires a TOTP code"
                    )
                payload = {"code": await self._totp_code()}
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

    async def _totp_code(self) -> str:
        """Return a TOTP code for a time step that was not used before.

        Magister rejects a code that was already used, so a second login within the
        same 30 s step waits for the next one.
        """
        assert self._totp_secret is not None
        step = int(self._wall_clock() // TOTP_PERIOD)
        if self._last_totp_step is not None and step <= self._last_totp_step:
            wait = (self._last_totp_step + 1) * TOTP_PERIOD - self._wall_clock()
            _LOGGER.debug("Waiting %.0fs for a fresh TOTP time step", max(wait, 0))
            await self._sleep(min(max(wait, 0) + 0.5, TOTP_PERIOD + 1))
            step = max(int(self._wall_clock() // TOTP_PERIOD), self._last_totp_step + 1)
        try:
            code = pyotp.TOTP(self._totp_secret, interval=TOTP_PERIOD).at(
                step * TOTP_PERIOD
            )
        except ValueError as err:  # binascii.Error: malformed base32 secret
            raise MagisterAuthError(
                AUTH_INVALID_TOTP, "The TOTP secret is not valid base32"
            ) from err
        self._last_totp_step = step
        return code

    def _raise_for_error(self, error: str) -> None:
        if error in _AUTH_CODE_ERRORS:
            if self._password_sent:
                raise MagisterApiError(
                    f"Magister rejected the login request code ({error})"
                )
            raise _AuthCodeRejectedError
        if error in _WRONG_CODE:
            raise MagisterAuthError(
                AUTH_INVALID_TOTP, f"TOTP code rejected ({error})", error
            )
        if error in _WRONG_CREDENTIALS:
            raise MagisterAuthError(AUTH_INVALID, f"Login rejected ({error})", error)
        if error in _UNSUPPORTED:
            raise MagisterAuthError(
                AUTH_UNSUPPORTED_LOGIN, f"Login method not supported ({error})", error
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

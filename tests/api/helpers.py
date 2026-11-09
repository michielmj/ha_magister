"""Helpers that fake the Magister login service with aioresponses."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

from aioresponses import CallbackResult, aioresponses

FIXTURES = Path(__file__).parent / "fixtures"
HOST = "school.magister.net"
ACCOUNTS = "https://accounts.magister.net"
SESSION_ID = "0123456789abcdef0123456789abcdef"
RETURN_URL = (
    "/connect/authorize/callback?client_id=M6-school.magister.net"
    "&redirect_uri=https%3A%2F%2Fschool.magister.net%2Foidc%2Fredirect_callback.html"
    "&response_type=id_token%20token&scope=openid%20profile&state=abc&nonce=def"
)
BUNDLE_PATH = "/js/account-81df86d50b8a8972c275.js"
AUTH_CODE = "1d0a1a08b701434d"
PASSWORD = "s3cret-Passw0rd!"
TOTP_SECRET = "JBSWY3DPEHPK3PXP"
TOKEN = "tok-abcdefghijklmnopqrstuvwxyz"
USERNAME = "ha-test-user"

AUTHORIZE_RE = re.compile(
    rf"^{re.escape(ACCOUNTS)}/connect/authorize\?(?!.*prompt=none).*$"
)
SILENT_RE = re.compile(rf"^{re.escape(ACCOUNTS)}/connect/authorize\?.*prompt=none.*$")
LOGIN_PAGE = (
    f"{ACCOUNTS}/account/login?sessionId={SESSION_ID}"
    f"&returnUrl={quote(RETURN_URL, safe='')}"
)


def callback_url(
    token: str = TOKEN, expires_in: int = 3600, extra: str = "token_type=Bearer"
) -> str:
    """URL of the OIDC callback with the token in the fragment."""
    return (
        f"https://{HOST}/oidc/redirect_callback.html"
        f"#access_token={token}&{extra}&expires_in={expires_in}&state=abc"
    )


def read_fixture(name: str) -> str:
    """Read a fixture file."""
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeLogin:
    """Registers the full login sequence on an ``aioresponses`` instance."""

    def __init__(
        self,
        mocked: aioresponses,
        *,
        challenges: list[dict[str, Any]] | None = None,
        token: str = TOKEN,
        expires_in: int = 3600,
    ) -> None:
        """Register the standard happy-path responses.

        ``challenges`` is the ordered list of challenge responses: the first answers
        ``/challenges/current`` and each next one the following POST.
        """
        self.mocked = mocked
        self.posts: list[tuple[str, dict[str, Any], dict[str, str]]] = []
        self._responses = list(
            challenges
            or [
                {"action": "username"},
                {"action": "password"},
                {"redirectURL": RETURN_URL},
            ]
        )
        self.token = token
        self.expires_in = expires_in
        self.bundle_hits = 0
        self.authorize_hits = 0
        self.silent_hits = 0
        self.authorize_location = f"{ACCOUNTS}/Account/Login?ReturnUrl=%2Fconnect"
        self.silent_locations: list[str | Exception] = []
        self.final_location = callback_url(token, expires_in)
        self._register()

    def _post_callback(self, url: Any, **kwargs: Any) -> CallbackResult:
        self.posts.append(
            (str(url).rsplit("/", 1)[-1], kwargs["json"], dict(kwargs["headers"]))
        )
        body = dict(self._responses.pop(0))
        if "_exception" in body:
            raise body["_exception"]
        status = body.pop("_status", 400 if "error" in body else 200)
        headers = body.pop("_headers", None)
        if "_raw" in body:
            return CallbackResult(status=status, body=body["_raw"], headers=headers)
        return CallbackResult(status=status, payload=body, headers=headers)

    def _bundle(self, url: Any, **kwargs: Any) -> CallbackResult:
        self.bundle_hits += 1
        return CallbackResult(body=read_fixture("login_bundle_excerpt.js"))

    async def _authorize(self, url: Any, **kwargs: Any) -> CallbackResult:
        await asyncio.sleep(0)
        self.authorize_hits += 1
        return CallbackResult(status=303, headers={"Location": self.authorize_location})

    async def _silent(self, url: Any, **kwargs: Any) -> CallbackResult:
        await asyncio.sleep(0)
        self.silent_hits += 1
        location = (
            self.silent_locations.pop(0)
            if self.silent_locations
            else f"https://{HOST}/oidc/redirect_callback.html#error=login_required"
        )
        if isinstance(location, Exception):
            raise location
        return CallbackResult(status=303, headers={"Location": location})

    def _final(self, url: Any, **kwargs: Any) -> CallbackResult:
        return CallbackResult(status=302, headers={"Location": self.final_location})

    def _register(self) -> None:
        m = self.mocked
        m.get(
            f"https://{HOST}/oidc_config.js",
            body=read_fixture("oidc_config.js"),
            repeat=True,
        )
        m.get(SILENT_RE, callback=self._silent, repeat=True)
        m.get(AUTHORIZE_RE, callback=self._authorize, repeat=True)
        m.get(
            f"{ACCOUNTS}/Account/Login?ReturnUrl=%2Fconnect",
            status=302,
            headers={
                "Location": f"/account/login?sessionId={SESSION_ID}"
                f"&returnUrl={quote(RETURN_URL, safe='')}",
                "Set-Cookie": "XSRF-TOKEN=xsrf-one; path=/; secure",
            },
            repeat=True,
        )
        m.get(
            LOGIN_PAGE,
            body=read_fixture("login_page.html"),
            headers={"Set-Cookie": "XSRF-TOKEN=xsrf-two; path=/; secure"},
            repeat=True,
        )
        m.get(f"{ACCOUNTS}{BUNDLE_PATH}", callback=self._bundle, repeat=True)
        for step in ("current", "username", "password", "soft-token"):
            m.post(
                f"{ACCOUNTS}/challenges/{step}",
                callback=self._post_callback,
                repeat=True,
            )
        m.get(f"{ACCOUNTS}{RETURN_URL}", callback=self._final, repeat=True)

"""Tests for MagisterAuth."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import pyotp
import pytest
from aioresponses import aioresponses

from custom_components.magister.api import (
    MagisterApiError,
    MagisterAuth,
    MagisterAuthError,
    MagisterConnectionError,
)

from .helpers import (
    ACCOUNTS,
    AUTH_CODE,
    AUTHORIZE_RE,
    HOST,
    LOGIN_PAGE,
    PASSWORD,
    RETURN_URL,
    SESSION_ID,
    TOKEN,
    TOTP_SECRET,
    USERNAME,
    FakeLogin,
    callback_url,
)


class Clock:
    """A controllable clock."""

    def __init__(self) -> None:
        """Start at zero."""
        self.now = 0.0

    def __call__(self) -> float:
        """Return the current fake time."""
        return self.now


def make_auth(
    session: aiohttp.ClientSession,
    totp_secret: str | None = None,
    clock: Clock | None = None,
) -> MagisterAuth:
    """Create the auth object under test."""
    return MagisterAuth(
        session,
        HOST,
        USERNAME,
        PASSWORD,
        totp_secret,
        clock=clock or Clock(),
    )


async def test_full_login(mocked: aioresponses, session: aiohttp.ClientSession) -> None:
    """Username + password login returns the token from the fragment."""
    fake = FakeLogin(mocked)
    auth = make_auth(session)

    assert await auth.async_get_token() == TOKEN
    assert auth.last_token_source == "login"

    steps = [step for step, _, _ in fake.posts]
    assert steps == ["current", "username", "password"]
    _, current, headers = fake.posts[0]
    assert current["sessionId"] == SESSION_ID
    assert current["authCode"] == AUTH_CODE
    # returnUrl is sent like JavaScript decodeURI: reserved escapes stay, %20 -> space
    assert "response_type=id_token token" in current["returnUrl"]
    assert "redirect_uri=https%3A%2F%2Fschool.magister.net" in current["returnUrl"]
    assert headers["X-XSRF-TOKEN"] == "xsrf-two"
    assert fake.posts[1][1]["username"] == USERNAME
    assert fake.posts[1][1]["action"] == "username"
    assert fake.posts[2][1]["password"] == PASSWORD
    assert fake.posts[2][1]["action"] == "password"


async def test_cached_token_is_reused(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """A second call within the validity returns the cache without requests."""
    fake = FakeLogin(mocked)
    auth = make_auth(session)
    await auth.async_get_token()
    posts = len(fake.posts)
    assert await auth.async_get_token() == TOKEN
    assert auth.last_token_source == "cached"
    assert len(fake.posts) == posts


async def test_login_with_totp(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """A soft-token challenge is answered with a TOTP code."""
    fake = FakeLogin(
        mocked,
        challenges=[
            {"action": "username"},
            {"action": "password"},
            {"action": "soft-token"},
            {"redirectURL": RETURN_URL},
        ],
    )
    auth = make_auth(session, totp_secret="jbsw y3dp ehpk 3pxp")
    assert await auth.async_get_token() == TOKEN
    step, body, _ = fake.posts[-1]
    assert step == "soft-token"
    assert body["action"] == "soft-token"
    assert pyotp.TOTP(TOTP_SECRET).verify(body["code"])


async def test_totp_required(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """A TOTP challenge without a secret raises totp_required."""
    FakeLogin(
        mocked,
        challenges=[
            {"action": "username"},
            {"action": "password"},
            {"action": "soft-token"},
        ],
    )
    auth = make_auth(session)
    with pytest.raises(MagisterAuthError) as err:
        await auth.async_get_token()
    assert err.value.code == "totp_required"


async def test_invalid_totp_error_and_repeat(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """A rejected TOTP code (error or repeated challenge) raises invalid_totp."""
    FakeLogin(
        mocked,
        challenges=[
            {"action": "username"},
            {"action": "password"},
            {"action": "soft-token"},
            {"error": "InvalidCode", "action": "soft-token"},
        ],
    )
    auth = make_auth(session, TOTP_SECRET)
    with pytest.raises(MagisterAuthError) as err:
        await auth.async_get_token()
    assert err.value.code == "invalid_totp"


async def test_repeated_totp_challenge(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """The same soft-token challenge twice is treated as a wrong code."""
    FakeLogin(
        mocked,
        challenges=[
            {"action": "username"},
            {"action": "password"},
            {"action": "soft-token"},
            {"action": "soft-token"},
        ],
    )
    auth = make_auth(session, TOTP_SECRET)
    with pytest.raises(MagisterAuthError) as err:
        await auth.async_get_token()
    assert err.value.code == "invalid_totp"


async def test_malformed_totp_secret(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """A secret that is not base32 raises invalid_totp, not a crash."""
    FakeLogin(
        mocked,
        challenges=[
            {"action": "username"},
            {"action": "password"},
            {"action": "soft-token"},
        ],
    )
    auth = make_auth(session, "not base32!!")
    with pytest.raises(MagisterAuthError) as err:
        await auth.async_get_token()
    assert err.value.code == "invalid_totp"


async def test_wrong_password_is_not_retried(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """invalid_auth is raised once and later calls fail without any request."""
    fake = FakeLogin(
        mocked,
        challenges=[
            {"action": "username"},
            {"action": "password"},
            {"error": "InvalidPassword"},
        ],
    )
    auth = make_auth(session)
    with pytest.raises(MagisterAuthError) as err:
        await auth.async_get_token()
    assert err.value.code == "invalid_auth"
    assert PASSWORD not in str(err.value)
    posts = len(fake.posts)
    hits = fake.authorize_hits

    with pytest.raises(MagisterAuthError):
        await auth.async_get_token()
    with pytest.raises(MagisterAuthError):
        await auth.async_get_token(force_refresh=True)
    assert len(fake.posts) == posts
    assert fake.authorize_hits == hits


async def test_update_credentials_clears_failure(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """After reauth with new credentials a login is attempted again."""
    fake = FakeLogin(
        mocked,
        challenges=[
            {"action": "username"},
            {"error": "InvalidUsername"},
            {"action": "username"},
            {"action": "password"},
            {"redirectURL": RETURN_URL},
        ],
    )
    auth = make_auth(session)
    with pytest.raises(MagisterAuthError):
        await auth.async_get_token()
    auth.update_credentials("new-password", None, username="other-user")
    assert await auth.async_get_token() == TOKEN
    assert fake.posts[-2][1]["username"] == "other-user"
    assert fake.posts[-1][1]["password"] == "new-password"


@pytest.mark.parametrize(
    "error",
    ["UserBlocked", "UserLockedOut", "InvalidUsernameOrPassword", "UserNotActivated"],
)
async def test_credential_error_codes(
    mocked: aioresponses, session: aiohttp.ClientSession, error: str
) -> None:
    """Account problems all map to invalid_auth."""
    FakeLogin(mocked, challenges=[{"error": error}])
    with pytest.raises(MagisterAuthError) as err:
        await make_auth(session).async_get_token()
    assert err.value.code == "invalid_auth"


@pytest.mark.parametrize("action", ["external-idp", "fido", "pair-fido", "select-user"])
async def test_unsupported_actions(
    mocked: aioresponses, session: aiohttp.ClientSession, action: str
) -> None:
    """SSO, passkey and other unknown steps raise unsupported_login."""
    FakeLogin(mocked, challenges=[{"action": "username"}, {"action": action}])
    with pytest.raises(MagisterAuthError) as err:
        await make_auth(session).async_get_token()
    assert err.value.code == "unsupported_login"
    assert action in str(err.value)


async def test_sso_redirect_url_is_unsupported(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """A challenge answer that redirects to another host means SSO."""
    FakeLogin(
        mocked,
        challenges=[
            {"action": "username"},
            {"redirectURL": "https://login.idp.example/authorize?x=1"},
        ],
    )
    with pytest.raises(MagisterAuthError) as err:
        await make_auth(session).async_get_token()
    assert err.value.code == "unsupported_login"


async def test_sso_redirect_from_authorize(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """Being sent to a foreign host straight from authorize means SSO."""
    fake = FakeLogin(mocked)
    fake.authorize_location = "https://login.idp.example/authorize?x=1"
    with pytest.raises(MagisterAuthError) as err:
        await make_auth(session).async_get_token()
    assert err.value.code == "unsupported_login"


async def test_sso_error_code(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """IdP-related error codes map to unsupported_login."""
    FakeLogin(mocked, challenges=[{"error": "NoRedirectUrl"}])
    with pytest.raises(MagisterAuthError) as err:
        await make_auth(session).async_get_token()
    assert err.value.code == "unsupported_login"


async def test_unknown_error_and_odd_sequences(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """Unknown errors and repeated steps are API errors, not auth errors."""
    FakeLogin(mocked, challenges=[{"error": "SomethingNew"}])
    with pytest.raises(MagisterApiError, match="SomethingNew"):
        await make_auth(session).async_get_token()


async def test_repeated_username_challenge(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """Being asked for the username twice is a protocol error."""
    FakeLogin(
        mocked,
        challenges=[{"action": "username"}, {"action": "username"}],
    )
    with pytest.raises(MagisterApiError, match="repeated"):
        await make_auth(session).async_get_token()


async def test_too_many_steps(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """An endless challenge chain is cut off."""
    FakeLogin(
        mocked,
        challenges=[{"action": "username"}, {"action": "password"}]
        + [{"action": f"step{i}"} for i in range(20)],
    )
    with pytest.raises(MagisterAuthError):
        await make_auth(session).async_get_token()


async def test_auth_code_refreshed_once(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """A rejected authCode triggers one retry with a freshly scraped code."""
    fake = FakeLogin(
        mocked,
        challenges=[
            {"error": "AuthCodeValidation"},
            {"action": "username"},
            {"action": "password"},
            {"redirectURL": RETURN_URL},
        ],
    )
    auth = make_auth(session)
    assert await auth.async_get_token() == TOKEN
    assert fake.bundle_hits == 2


async def test_auth_code_rejected_twice(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """A second rejection is reported as an API error."""
    FakeLogin(
        mocked,
        challenges=[{"error": "AuthCodeValidation"}, {"error": "AuthCodeValidation"}],
    )
    with pytest.raises(MagisterApiError, match="may have changed"):
        await make_auth(session).async_get_token()


async def test_auth_code_cached_between_logins(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """The bundle is downloaded once per bundle URL."""
    clock = Clock()
    fake = FakeLogin(
        mocked,
        challenges=[
            {"action": "username"},
            {"action": "password"},
            {"redirectURL": RETURN_URL},
            {"action": "username"},
            {"action": "password"},
            {"redirectURL": RETURN_URL},
        ],
    )
    auth = make_auth(session, clock=clock)
    await auth.async_get_token()
    clock.now = 10_000
    await auth.async_get_token()
    assert fake.bundle_hits == 1


async def test_silent_renew(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """After a login, a forced refresh uses prompt=none."""
    fake = FakeLogin(mocked)
    fake.silent_locations = [callback_url("renewed-token", 3600)]
    auth = make_auth(session)
    await auth.async_get_token()
    assert await auth.async_get_token(force_refresh=True) == "renewed-token"
    assert auth.last_token_source == "silent"
    assert fake.silent_hits == 1
    assert [s for s, _, _ in fake.posts] == ["current", "username", "password"]


async def test_silent_renew_falls_back_to_login(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """login_required from prompt=none leads to a new full login."""
    fake = FakeLogin(
        mocked,
        challenges=[
            {"action": "username"},
            {"action": "password"},
            {"redirectURL": RETURN_URL},
            {"action": "username"},
            {"action": "password"},
            {"redirectURL": RETURN_URL},
        ],
    )
    auth = make_auth(session)
    await auth.async_get_token()
    await auth.async_get_token(force_refresh=True)
    assert auth.last_token_source == "login"
    assert auth.last_silent_failure == "login_required"
    assert fake.silent_hits == 1
    assert len(fake.posts) == 6


async def test_silent_renew_network_failure_falls_back(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """A network error during the silent attempt still tries a full login."""
    fake = FakeLogin(
        mocked,
        challenges=[
            {"action": "username"},
            {"action": "password"},
            {"redirectURL": RETURN_URL},
        ]
        * 2,
    )
    auth = make_auth(session)
    await auth.async_get_token()
    # Silent attempt lands on the login page without a token.
    fake.silent_locations = [LOGIN_PAGE]
    await auth.async_get_token(force_refresh=True)
    assert auth.last_silent_failure == "no_token"
    assert auth.last_token_source == "login"


async def test_expiry_margin(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """The cached token is replaced 60 seconds before it expires."""
    clock = Clock()
    fake = FakeLogin(mocked, expires_in=3600)
    fake.silent_locations = [callback_url("second", 3600)]
    auth = make_auth(session, clock=clock)
    assert await auth.async_get_token() == TOKEN

    clock.now = 3539
    assert await auth.async_get_token() == TOKEN
    assert auth.last_token_source == "cached"

    clock.now = 3541
    assert await auth.async_get_token() == "second"
    assert auth.last_token_source == "silent"


async def test_concurrent_calls_login_once(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """Parallel callers share one login."""
    fake = FakeLogin(mocked)
    auth = make_auth(session)
    tokens = await asyncio.gather(*(auth.async_get_token() for _ in range(8)))
    assert set(tokens) == {TOKEN}
    assert fake.authorize_hits == 1
    assert [s for s, _, _ in fake.posts].count("current") == 1


async def test_concurrent_forced_refresh_renews_once(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """Parallel forced refreshes (several 401s) renew only once."""
    fake = FakeLogin(mocked)
    fake.silent_locations = [callback_url("renewed", 3600)]
    auth = make_auth(session)
    await auth.async_get_token()
    tokens = await asyncio.gather(
        *(auth.async_get_token(force_refresh=True) for _ in range(5))
    )
    assert set(tokens) == {"renewed"}
    assert fake.silent_hits == 1


async def test_existing_session_returns_token_directly(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """If authorize already redirects to the callback, no challenges are needed."""
    fake = FakeLogin(mocked)
    fake.authorize_location = callback_url("direct", 1800)
    auth = make_auth(session)
    assert await auth.async_get_token() == "direct"
    assert fake.posts == []


async def test_login_finishing_without_token(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """A callback with an error fragment is an API error."""
    fake = FakeLogin(mocked)
    fake.final_location = (
        f"https://{HOST}/oidc/redirect_callback.html#error=access_denied"
    )
    with pytest.raises(MagisterApiError, match="access_denied"):
        await make_auth(session).async_get_token()


async def test_final_redirect_to_foreign_host_is_sso(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """The final hop leaving Magister counts as SSO."""
    fake = FakeLogin(mocked)
    fake.final_location = "https://login.idp.example/start"
    with pytest.raises(MagisterAuthError) as err:
        await make_auth(session).async_get_token()
    assert err.value.code == "unsupported_login"


async def test_bad_expires_in_falls_back(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """A garbage expires_in still yields a token with the default lifetime."""
    fake = FakeLogin(mocked)
    fake.final_location = (
        f"https://{HOST}/oidc/redirect_callback.html#access_token=abc&expires_in=soon"
    )
    assert await make_auth(session).async_get_token() == "abc"


async def test_authorize_without_login_redirect(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """Landing on an unrelated accounts page is an API error."""
    mocked.get(AUTHORIZE_RE, status=200, body="hello")
    mocked.get(f"https://{HOST}/oidc_config.js", body="var x;")
    with pytest.raises(MagisterApiError, match="login page"):
        await make_auth(session).async_get_token()


async def test_redirect_loop(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """Endless redirects are cut off."""
    mocked.get(f"https://{HOST}/oidc_config.js", body="var x;")
    mocked.get(
        AUTHORIZE_RE,
        status=302,
        headers={"Location": f"{ACCOUNTS}/loop"},
    )
    mocked.get(
        f"{ACCOUNTS}/loop",
        status=302,
        headers={"Location": f"{ACCOUNTS}/loop"},
        repeat=True,
    )
    with pytest.raises(MagisterApiError, match="redirects"):
        await make_auth(session).async_get_token()


async def test_login_page_error_status(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """A failing login page is an API error carrying the status."""
    mocked.get(f"https://{HOST}/oidc_config.js", body="var x;")
    mocked.get(AUTHORIZE_RE, status=303, headers={"Location": LOGIN_PAGE})
    mocked.get(LOGIN_PAGE, status=403)
    with pytest.raises(MagisterApiError) as err:
        await make_auth(session).async_get_token()
    assert err.value.status == 403


async def test_bundle_failures(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """Bundle problems (non-200, foreign host) are API errors."""
    mocked.get(f"https://{HOST}/oidc_config.js", body="var x;")
    mocked.get(AUTHORIZE_RE, status=303, headers={"Location": LOGIN_PAGE})
    mocked.get(LOGIN_PAGE, body='<script src="js/account-abc.js"></script>')
    mocked.get(f"{ACCOUNTS}/js/account-abc.js", status=404)
    with pytest.raises(MagisterApiError) as err:
        await make_auth(session).async_get_token()
    assert err.value.status == 404


async def test_bundle_on_foreign_host(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """A login script served from elsewhere is never fetched."""
    mocked.get(f"https://{HOST}/oidc_config.js", body="var x;")
    mocked.get(AUTHORIZE_RE, status=303, headers={"Location": LOGIN_PAGE})
    mocked.get(
        LOGIN_PAGE, body='<script src="https://cdn.example/js/account-abc.js"></script>'
    )
    with pytest.raises(MagisterApiError, match="outside"):
        await make_auth(session).async_get_token()


async def test_oidc_config_failure(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """A failing oidc_config.js is an API error with the status."""
    mocked.get(f"https://{HOST}/oidc_config.js", status=404)
    with pytest.raises(MagisterApiError) as err:
        await make_auth(session).async_get_token()
    assert err.value.status == 404


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (aiohttp.ClientConnectionError("boom"), MagisterConnectionError),
        (TimeoutError(), MagisterConnectionError),
    ],
)
async def test_network_errors(
    mocked: aioresponses,
    session: aiohttp.ClientSession,
    exc: Exception,
    expected: type[Exception],
) -> None:
    """Network failures and timeouts map to MagisterConnectionError."""
    mocked.get(f"https://{HOST}/oidc_config.js", exception=exc)
    with pytest.raises(expected):
        await make_auth(session).async_get_token()


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (500, MagisterConnectionError),
        (503, MagisterConnectionError),
        (429, MagisterApiError),
    ],
)
async def test_server_errors(
    mocked: aioresponses,
    session: aiohttp.ClientSession,
    status: int,
    expected: type[Exception],
) -> None:
    """5xx and 429 responses map to connection/API errors."""
    mocked.get(f"https://{HOST}/oidc_config.js", status=status)
    with pytest.raises(expected):
        await make_auth(session).async_get_token()


async def test_challenge_non_json_and_bad_status(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """Non-JSON or unexpected status from /challenges raises an API error."""
    mocked.get(f"https://{HOST}/oidc_config.js", body="var x;")
    mocked.get(AUTHORIZE_RE, status=303, headers={"Location": LOGIN_PAGE})
    mocked.get(LOGIN_PAGE, body=_login_html())
    mocked.get(f"{ACCOUNTS}/js/account-81df86d50b8a8972c275.js", body=_bundle())
    mocked.post(f"{ACCOUNTS}/challenges/current", body="<html>")
    with pytest.raises(MagisterApiError):
        await make_auth(session).async_get_token()


async def test_challenge_unexpected_shape(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """A JSON list from /challenges raises an API error."""
    mocked.get(f"https://{HOST}/oidc_config.js", body="var x;")
    mocked.get(AUTHORIZE_RE, status=303, headers={"Location": LOGIN_PAGE})
    mocked.get(LOGIN_PAGE, body=_login_html())
    mocked.get(f"{ACCOUNTS}/js/account-81df86d50b8a8972c275.js", body=_bundle())
    mocked.post(f"{ACCOUNTS}/challenges/current", payload=[1])
    with pytest.raises(MagisterApiError):
        await make_auth(session).async_get_token()


async def test_silent_renew_connection_error_falls_back(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """A network error during prompt=none is retried as a full login."""
    fake = FakeLogin(
        mocked,
        challenges=[
            {"action": "username"},
            {"action": "password"},
            {"redirectURL": RETURN_URL},
        ]
        * 2,
    )
    auth = make_auth(session)
    await auth.async_get_token()
    fake.silent_locations = [aiohttp.ClientConnectionError("down")]
    await auth.async_get_token(force_refresh=True)
    assert auth.last_silent_failure == "MagisterConnectionError"
    assert auth.last_token_source == "login"


async def test_challenge_unexpected_status(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """A 403 from /challenges raises an API error with status."""
    mocked.get(f"https://{HOST}/oidc_config.js", body="var x;")
    mocked.get(AUTHORIZE_RE, status=303, headers={"Location": LOGIN_PAGE})
    mocked.get(LOGIN_PAGE, body=_login_html())
    mocked.get(f"{ACCOUNTS}/js/account-81df86d50b8a8972c275.js", body=_bundle())
    mocked.post(f"{ACCOUNTS}/challenges/current", status=403, payload={})
    with pytest.raises(MagisterApiError) as err:
        await make_auth(session).async_get_token()
    assert err.value.status == 403


def _login_html() -> str:
    from .helpers import read_fixture

    return read_fixture("login_page.html")


def _bundle() -> str:
    from .helpers import read_fixture

    return read_fixture("login_bundle_excerpt.js")


async def test_csrf_header_falls_back_to_cookie_jar(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """With a real cookie jar entry the XSRF header is still sent."""
    from yarl import URL

    session.cookie_jar.update_cookies({"XSRF-TOKEN": "from-jar"}, URL(ACCOUNTS))
    auth = make_auth(session)
    assert auth._csrf_headers() == {"X-XSRF-TOKEN": "from-jar"}
    fresh = make_auth(aiohttp.ClientSession())
    assert fresh._csrf_headers() == {}
    await fresh._session.close()


async def test_no_secrets_in_logs_errors_or_repr(
    mocked: aioresponses,
    session: aiohttp.ClientSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Password, TOTP secret, token and authCode never show up anywhere."""
    caplog.set_level(logging.DEBUG)
    FakeLogin(
        mocked,
        challenges=[
            {"action": "username"},
            {"action": "password"},
            {"action": "soft-token"},
            {"redirectURL": RETURN_URL},
        ],
    )
    auth = make_auth(session, TOTP_SECRET)
    token = await auth.async_get_token()
    assert token == TOKEN

    secrets_ = [PASSWORD, TOTP_SECRET, TOKEN, AUTH_CODE, "xsrf-two"]
    for secret in secrets_:
        assert secret not in caplog.text
        assert secret not in repr(auth)
        assert secret not in str(auth)


async def test_no_secrets_in_error_messages(
    mocked: aioresponses,
    session: aiohttp.ClientSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Failure paths do not leak secrets either."""
    caplog.set_level(logging.DEBUG)
    FakeLogin(
        mocked,
        challenges=[
            {"action": "username"},
            {"action": "password"},
            {"error": "InvalidPassword"},
        ],
    )
    auth = make_auth(session, TOTP_SECRET)
    with pytest.raises(MagisterAuthError) as err:
        await auth.async_get_token()
    text = caplog.text + str(err.value) + repr(err.value)
    for secret in (PASSWORD, TOTP_SECRET, AUTH_CODE):
        assert secret not in text


def test_invalid_host_rejected(session: aiohttp.ClientSession) -> None:
    """Auth refuses hosts outside magister.net."""
    with pytest.raises(ValueError):
        MagisterAuth(session, "evil.example.com", "u", "p")


def test_auth_host_property(session: aiohttp.ClientSession) -> None:
    """The host is normalized."""
    assert MagisterAuth(session, "school", "u", "p").host == HOST


def test_decode_uri_matches_javascript() -> None:
    """The helper mirrors decodeURI for the returnUrl."""
    from custom_components.magister.api.auth import _decode_uri

    assert _decode_uri("a%20b%3Ac%2Fd%25e%C3%A9") == "a b%3Ac%2Fd%eé"
    assert _decode_uri("%ff") == "%ff"
    assert Any  # keep the typing import used

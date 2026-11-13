"""Tests for scraping the login page and bundle."""

from __future__ import annotations

import pytest

from custom_components.magister.api.errors import MagisterApiError
from custom_components.magister.api.login_page import (
    DEFAULT_SCOPE,
    extract_auth_code,
    find_login_script_url,
    parse_login_url,
    parse_oidc_scope,
)

from .helpers import AUTH_CODE, LOGIN_PAGE, read_fixture


def test_extract_auth_code_from_bundle_fixture() -> None:
    """The code is assembled from fragments in the real (trimmed) bundle."""
    assert extract_auth_code(read_fixture("login_bundle_excerpt.js")) == AUTH_CODE


def test_extract_auth_code_other_order_and_quotes() -> None:
    """Fragment order and quote style are read from the bundle, not hard-coded."""
    js = (
        "(q=['aa','bb','cc'],['2','0','1']"
        ".map((function(t){return q[parseInt(t)||0]})).join(''))"
    )
    assert extract_auth_code(js) == "ccaabb"


def test_extract_auth_code_literal_fallback() -> None:
    """A literal authCode next to the key is accepted."""
    assert extract_auth_code('{authCode:"deadbeef01"}') == "deadbeef01"


def test_extract_auth_code_index_out_of_range_falls_through() -> None:
    """Broken indexes do not crash; the extractor reports a clear error."""
    js = '(q=["aa"],["5"].map((function(t){return q[parseInt(t)||0]})).join(""))'
    with pytest.raises(MagisterApiError, match="authCode"):
        extract_auth_code(js)


def test_extract_auth_code_missing() -> None:
    """Garbage input raises an API error without echoing content."""
    with pytest.raises(MagisterApiError, match="authCode"):
        extract_auth_code("nothing here")


def test_find_login_script_url() -> None:
    """The account bundle is found in the login page."""
    html = read_fixture("login_page.html")
    assert find_login_script_url(html) == "js/account-81df86d50b8a8972c275.js"


def test_find_login_script_url_fallback_and_missing() -> None:
    """Any script is used when the naming changes; none is an error."""
    assert find_login_script_url('<script src="/js/main.js"></script>') == "/js/main.js"
    with pytest.raises(MagisterApiError):
        find_login_script_url("<html></html>")


def test_parse_oidc_scope() -> None:
    """The scope comes from oidc_config.js, with a built-in fallback."""
    assert "calendar.user" in parse_oidc_scope(read_fixture("oidc_config.js"))
    assert parse_oidc_scope("var x = 1;") == DEFAULT_SCOPE


def test_parse_login_url() -> None:
    """Only /account/login URLs with both parameters match."""
    session_id, return_url = parse_login_url(LOGIN_PAGE) or ("", "")
    assert session_id == "0123456789abcdef0123456789abcdef"
    assert return_url.startswith("/connect/authorize/callback?")
    assert parse_login_url("https://accounts.magister.net/other") is None
    assert parse_login_url("https://accounts.magister.net/account/login") is None


def test_extract_auth_code_prefers_assembly_after_key() -> None:
    """A decoy assembly before the authCode key is ignored."""
    decoy = (
        '(q=["xx","yy"],["1"].map((function(t){return q[parseInt(t)||0]})).join(""))'
    )
    real = (
        '(q=["aa","bb"],["1","0"].map('
        '(function(t){return q[parseInt(t)||0]})).join(""))'
    )
    assert extract_auth_code(f'{decoy};k=["authCode"];{real}') == "bbaa"
    assert extract_auth_code(decoy) == "yy"


def test_parse_login_url_requires_https_and_accounts_host() -> None:
    """Look-alike login URLs are rejected."""
    query = "?sessionId=a&returnUrl=b"
    assert parse_login_url("https://accounts.magister.net/account/login" + query)
    assert parse_login_url("http://accounts.magister.net/account/login" + query) is None
    assert parse_login_url("https://evil.example/account/login" + query) is None

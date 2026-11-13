"""Scraping helpers for the Magister login page and its JavaScript bundle.

Everything here is pure string parsing (no I/O) so it can be tested against saved
fixtures. Magister can change these patterns at any time; this is the module to fix
when ``MagisterLoginPageError`` starts to appear.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from .errors import MagisterLoginPageError

DEFAULT_SCOPE = (
    "openid profile opp.read opp.manage attendance.overview "
    "attendance.administration calendar.user calendar.ical.user "
    "calendar.to-do.user grades.read grades.manage oso.administration "
    "registration.admin lockers.administration exams.administration "
    "enrollment.admin privacyportal.administration learningmaterials.user"
)

_SCRIPT_SRC_RE = re.compile(r"<script\b[^>]*?\bsrc=[\"']([^\"']+\.js)[\"']", re.I)
_ACCOUNT_BUNDLE_RE = re.compile(r"(?:^|/)js/account-[\w-]+\.js$")

# Current form (2026-11): the code is assembled from string fragments:
#   a=["49","b701434d","1d0a1a08","e602"],
#   ["2","1"].map(function(t){return a[parseInt(t)||0]}).join("")
_ASSEMBLED_RE = re.compile(
    r"""\w+\s*=\s*\[\s*(?P<parts>(?:["'][^"']*["']\s*,?\s*)+)\]\s*,\s*
        \[\s*(?P<order>(?:["']?\d+["']?\s*,?\s*)+)\]\s*\.map\(
        [^;]{0,120}?parseInt\([^;]{0,120}?\.join\(\s*(?:""|'')\s*\)""",
    re.X,
)
# Older / alternative form: a literal next to the key.
_LITERAL_RE = re.compile(r"""["']?authCode["']?\s*[:=]\s*["']([0-9a-fA-F]{8,})["']""")
_STRING_RE = re.compile(r"""["']([^"']*)["']""")
_DIGITS_RE = re.compile(r"\d+")

_SCOPE_RE = re.compile(r"""\bscope\s*:\s*(["'])(?P<scope>.+?)\1""")


def find_login_script_url(html: str) -> str:
    """Return the (relative) URL of the login page's main JS bundle."""
    sources: list[str] = _SCRIPT_SRC_RE.findall(html)
    for source in sources:
        if _ACCOUNT_BUNDLE_RE.search(source):
            return source
    if sources:
        return sources[0]
    raise MagisterLoginPageError("Login page contains no script bundle")


def extract_auth_code(js: str) -> str:
    """Extract the current ``authCode`` from the login JavaScript bundle."""
    key = js.find("authCode")
    matches = list(_ASSEMBLED_RE.finditer(js))
    # Prefer the assembly closest after the "authCode" key name.
    match = next((m for m in matches if m.start() >= key >= 0), None) or (
        matches[0] if matches else None
    )
    if match:
        parts = _STRING_RE.findall(match.group("parts"))
        order = [int(i) for i in _DIGITS_RE.findall(match.group("order"))]
        try:
            code = "".join(parts[i] for i in order)
        except IndexError:
            code = ""
        if code:
            return code
    literal = _LITERAL_RE.search(js)
    if literal:
        return str(literal.group(1))
    raise MagisterLoginPageError("Could not extract authCode from the login bundle")


def parse_oidc_scope(oidc_config_js: str) -> str:
    """Return the OIDC scope string from the tenant's ``oidc_config.js``."""
    match = _SCOPE_RE.search(oidc_config_js)
    if match:
        return " ".join(str(match.group("scope")).split())
    return DEFAULT_SCOPE


def parse_login_url(url: str) -> tuple[str, str] | None:
    """Return ``(sessionId, returnUrl)`` of a ``/account/login`` URL, else ``None``."""
    parts = urlsplit(url)
    if (
        parts.scheme != "https"
        or parts.netloc != "accounts.magister.net"
        or parts.path.lower() != "/account/login"
    ):
        return None
    query = parse_qs(parts.query)
    session_id = query.get("sessionId", [""])[0]
    return_url = query.get("returnUrl", [""])[0]
    if not session_id or not return_url:
        return None
    return session_id, return_url

"""Constants for the Magister integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "magister"

CONF_SCHOOL: Final = "school"
CONF_TOTP_SECRET: Final = "totp_secret"
CONF_CHILDREN: Final = "children"
CONF_HOST: Final = "host"

# Keys of one item in ``CONF_CHILDREN``.
CHILD_ID: Final = "id"
CHILD_NAME: Final = "name"
CHILD_SHORT_NAME: Final = "short_name"

SCHOOL_SUFFIX: Final = ".magister.net"

# Fixed in M2; becomes configurable through the options flow in M3.
WEEKS_BACK: Final = 1
WEEKS_AHEAD: Final = 3
UPDATE_INTERVAL: Final = timedelta(minutes=30)

MANUFACTURER: Final = "Magister"


def host_prefix(host: str) -> str:
    """Return the school part of a host (``school`` for ``school.magister.net``)."""
    return host.removesuffix(SCHOOL_SUFFIX)

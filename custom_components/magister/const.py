"""Constants for the Magister integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "magister"

CONF_SCHOOL: Final = "school"
CONF_TOTP_SECRET: Final = "totp_secret"
CONF_CHILDREN: Final = "children"
CONF_HOST: Final = "host"
CONF_REMOVE_TOTP: Final = "remove_totp"

# Keys of one item in ``CONF_CHILDREN``.
CHILD_ID: Final = "id"
CHILD_NAME: Final = "name"
CHILD_SHORT_NAME: Final = "short_name"

SCHOOL_SUFFIX: Final = ".magister.net"

# Options (the options flow); the defaults apply to entries without options.
CONF_WEEKS_BACK: Final = "weeks_back"
CONF_WEEKS_AHEAD: Final = "weeks_ahead"
CONF_INTERVAL: Final = "update_interval"

WEEKS_BACK: Final = 1
WEEKS_AHEAD: Final = 3
INTERVAL_MINUTES: Final = 30
UPDATE_INTERVAL: Final = timedelta(minutes=INTERVAL_MINUTES)
WEEKS_BACK_MAX: Final = 8
WEEKS_AHEAD_MAX: Final = 12
INTERVAL_MIN: Final = 15
INTERVAL_MAX: Final = 360

# First-appointment sensors are config sub-entries.
SUBENTRY_FIRST: Final = "first_appointment"
CONF_CHILD_ID: Final = "child_id"
CONF_OFFSET: Final = "offset"
CONF_EXCLUDED: Final = "excluded"
OFFSET_FIELD_MAX: Final = 100

MANUFACTURER: Final = "Magister"


def host_prefix(host: str) -> str:
    """Return the school part of a host (``school`` for ``school.magister.net``)."""
    return host.removesuffix(SCHOOL_SUFFIX)


def max_offset(weeks_ahead: int) -> int:
    """Highest day offset (0 = today) that fits in a window of ``weeks_ahead``."""
    return 7 * weeks_ahead - 1

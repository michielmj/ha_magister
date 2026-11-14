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
# Homework weights: ``{child_id: {"types": {...}, "subjects": {...}}}``. Part of the
# options but not of the reload snapshot: changing them never reloads the entry.
CONF_WEIGHTS: Final = "weights"

WEEKS_BACK: Final = 1
# Manual label options: ``{child_id: [{"id", "name", "kind"}]}``. Like the weights, part
# of the options but not of the reload snapshot.
CONF_LABELS: Final = "labels"

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

# Homework planner service.
SERVICE_SET_HOMEWORK_PROGRESS: Final = "set_homework_progress"
ATTR_ITEM: Final = "item"
ATTR_PROGRESS: Final = "progress"
SERVICE_ADD_HOMEWORK_LABEL: Final = "add_homework_label"
SERVICE_REMOVE_HOMEWORK_LABEL: Final = "remove_homework_label"
ATTR_APPOINTMENT: Final = "appointment"
ATTR_LABEL: Final = "label"
ATTR_NOTE: Final = "note"
SERVICE_SET_HOMEWORK_OVERRIDE: Final = "set_homework_override"
ATTR_MODE: Final = "mode"

MANUFACTURER: Final = "Magister"

# Entities stay available on the last good data for this long after a failed refresh.
DATA_MAX_AGE: Final = timedelta(hours=24)


def host_prefix(host: str) -> str:
    """Return the school part of a host (``school`` for ``school.magister.net``)."""
    return host.removesuffix(SCHOOL_SUFFIX)


def max_offset(weeks_ahead: int) -> int:
    """Highest day offset (0 = today) that fits in a window of ``weeks_ahead``."""
    return 7 * weeks_ahead - 1

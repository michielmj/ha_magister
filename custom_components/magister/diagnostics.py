"""Diagnostics for Magister (no secrets, names, ids or host)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    CHILD_ID,
    CONF_CHILDREN,
    CONF_EXCLUDED,
    CONF_HOST,
    CONF_OFFSET,
    CONF_TOTP_SECRET,
    CONF_WEIGHTS,
)
from .coordinator import MagisterConfigEntry

# Redacted wherever they could turn up (also nested), in addition to leaving them out.
TO_REDACT = {
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_TOTP_SECRET,
    "school",
    "name",
    "short_name",
    "id",
    "child_id",
    "token",
    "access_token",
    "cookie",
}


def _account_type(entry: MagisterConfigEntry) -> str:
    """``student`` when the account holder is the only child, else ``parent``."""
    children = entry.data[CONF_CHILDREN]
    person_id = (entry.unique_id or "").rpartition(":")[2]
    if len(children) == 1 and str(children[0][CHILD_ID]) == person_id:
        return "student"
    return "parent"


def _counts(values: list[int | None]) -> dict[str, int]:
    return {str(key): count for key, count in sorted(Counter(values).items(), key=str)}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MagisterConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    auth = runtime.auth
    children: list[dict[str, Any]] = []
    for index, (child_id, appointments) in enumerate(
        (coordinator.data or {}).items(), start=1
    ):
        children.append(
            {
                "child": f"child {index}",
                "homework": runtime.homework.statistics(child_id),
                "events_in_window": len(appointments),
                "status": _counts([item.status for item in appointments]),
                "info_type": _counts([item.info_type for item in appointments]),
                "type": _counts([item.type for item in appointments]),
            }
        )
    last_exception = coordinator.last_exception
    diagnostics: dict[str, Any] = {
        "entry": {
            "account_type": _account_type(entry),
            "number_of_children": len(entry.data[CONF_CHILDREN]),
            # Weights are keyed by child id and subject: only their counts are shown.
            "options": {k: v for k, v in entry.options.items() if k != CONF_WEIGHTS},
        },
        "children": children,
        "homework_store": {"stored_entries": runtime.homework.stored_entries},
        "sensors": [
            {
                "offset": subentry.data.get(CONF_OFFSET),
                "excluded_subjects": len(subentry.data.get(CONF_EXCLUDED, [])),
            }
            for subentry in entry.subentries.values()
        ],
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_success": coordinator.last_success,
            "last_success_age_seconds": None
            if coordinator.last_success is None
            else round((dt_util.utcnow() - coordinator.last_success).total_seconds()),
            "last_error": type(last_exception).__name__ if last_exception else None,
            "update_interval": str(coordinator.update_interval),
        },
        "auth": {
            "token_source": auth.last_token_source,
            "silent_failure": auth.last_silent_failure,
            "backoff_remaining_seconds": round(auth.backoff_remaining),
            "final_failure": auth.has_final_failure,
            "final_failure_reported": auth.final_failure_reported,
            "login_page_changed": auth.login_page_changed,
            "password_submissions": auth.password_submissions,
        },
    }
    return async_redact_data(diagnostics, TO_REDACT)

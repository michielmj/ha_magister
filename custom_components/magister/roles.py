"""Who is linked to a child, and who may answer a proposal for the daily maximum.

Pure helpers on the stored coach settings of a child; shared by the AI coach and the
WebSocket API (which cannot import the coach module).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from .const import (
    COACH_PARENTS,
    COACH_STUDENTS,
    COACH_USERS,
    CONF_COACH,
)

if TYPE_CHECKING:
    from .coordinator import MagisterConfigEntry

# The role of a user for a child: Leerling (student) or Ouder (parent).
ROLE_STUDENT: Final = "student"
ROLE_PARENT: Final = "parent"

# Who answered a proposal: the student, or someone on behalf of a child that has no
# student user (a parent, or an administrator).
ANSWERED_BY_STUDENT: Final = "student"
ANSWERED_ON_BEHALF: Final = "on_behalf"


def coach_settings(entry: MagisterConfigEntry, child_id: int) -> dict[str, Any]:
    """The stored coach settings of a child (empty when none)."""
    stored = entry.options.get(CONF_COACH)
    settings = stored.get(str(child_id)) if isinstance(stored, dict) else None
    return settings if isinstance(settings, dict) else {}


def _users(settings: dict[str, Any], key: str) -> list[str]:
    raw = settings.get(key)
    return [u for u in raw if isinstance(u, str)] if isinstance(raw, list) else []


def student_users(settings: dict[str, Any]) -> list[str]:
    """The linked student (Leerling) users; the 1.6.0 ``users`` key counts as such."""
    key = (
        COACH_STUDENTS
        if isinstance(settings.get(COACH_STUDENTS), list)
        else COACH_USERS
    )
    return _users(settings, key)


def parent_users(settings: dict[str, Any]) -> list[str]:
    """The linked parent (Ouder) users."""
    return _users(settings, COACH_PARENTS)


def role_of(settings: dict[str, Any], user_id: str | None) -> str | None:
    """The role of a user for a child; ``None`` when not linked.

    A user in both lists (the options flow refuses that) gets the parent role, the
    one with fewer rights.
    """
    if not user_id:
        return None
    if user_id in parent_users(settings):
        return ROLE_PARENT
    if user_id in student_users(settings):
        return ROLE_STUDENT
    return None


def proposal_answerer(
    settings: dict[str, Any], user_id: str | None, *, is_admin: bool = False
) -> str | None:
    """How this user may answer a proposal for the daily maximum of the child.

    ``student`` for a user linked as Leerling. When the child has no Leerling user,
    ``on_behalf`` for a user linked as Ouder or an administrator. Otherwise ``None``:
    nobody else answers, and no parent while the child has a Leerling user.
    """
    role = role_of(settings, user_id)
    if role == ROLE_STUDENT:
        return ANSWERED_BY_STUDENT
    if student_users(settings):
        return None
    if role == ROLE_PARENT or is_admin:
        return ANSWERED_ON_BEHALF
    return None

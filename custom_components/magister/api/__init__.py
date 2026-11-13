"""Pure-Python Magister API client (no Home Assistant imports)."""

from .auth import MagisterAuth
from .client import MagisterClient
from .errors import (
    MagisterApiError,
    MagisterAuthError,
    MagisterConnectionError,
    MagisterError,
    MagisterLoginPageError,
)
from .first_appointment import FirstAppointment, find_first_appointment
from .mapping import CalendarFields, build_summary, lesson_hours, map_appointment
from .models import Account, Appointment, AppointmentType, InfoType, Person
from .utils import normalize_host

__all__ = [
    "Account",
    "Appointment",
    "AppointmentType",
    "CalendarFields",
    "FirstAppointment",
    "InfoType",
    "MagisterApiError",
    "MagisterAuth",
    "MagisterAuthError",
    "MagisterClient",
    "MagisterConnectionError",
    "MagisterError",
    "MagisterLoginPageError",
    "Person",
    "build_summary",
    "find_first_appointment",
    "lesson_hours",
    "map_appointment",
    "normalize_host",
]

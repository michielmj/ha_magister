"""Pure-Python Magister API client (no Home Assistant imports)."""

from .auth import MagisterAuth
from .client import MagisterClient
from .errors import (
    MagisterApiError,
    MagisterAuthError,
    MagisterConnectionError,
    MagisterError,
)
from .models import Account, Appointment, AppointmentType, InfoType, Person
from .utils import normalize_host

__all__ = [
    "Account",
    "Appointment",
    "AppointmentType",
    "InfoType",
    "MagisterApiError",
    "MagisterAuth",
    "MagisterAuthError",
    "MagisterClient",
    "MagisterConnectionError",
    "MagisterError",
    "Person",
    "normalize_host",
]

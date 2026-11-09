"""Anonymize Magister API responses so they can be shared and committed.

What is changed:

* person names: the account holder of a parent account becomes ``Ouder``, children
  become ``Kind A``, ``Kind B``, ...
* person IDs and appointment IDs become stable fake numbers (the same real ID always
  maps to the same fake one within one :class:`Anonymizer`).
* teacher names and codes become ``Docent N`` / ``D<N>``.
* the school host name becomes ``school.example``.
* free text keeps its words, but e-mail addresses and URLs are removed.
* person objects are cut down to ID and name fields; links and attachments are
  neutralized.

Review the output before sharing it: free text (``Omschrijving``, ``Inhoud``) can still
contain names or other personal details that no tool can recognize.
"""

from __future__ import annotations

import re
import string
from typing import Any

SCHOOL_PLACEHOLDER = "school.example"
EMAIL_PLACEHOLDER = "email@example.invalid"
URL_PLACEHOLDER = "https://example.invalid/"

_EMAIL_RE = re.compile(r"[\w.+'-]+@[\w-]+(?:\.[\w-]+)+")
_URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"')]+", re.IGNORECASE)
_MAGISTER_HOST_RE = re.compile(r"[\w-]+\.magister\.net", re.IGNORECASE)

_PERSON_KEYS = frozenset(
    {"Id", "Roepnaam", "Tussenvoegsel", "Achternaam", "Voorletters"}
)
_TEACHER_KEYS = frozenset({"Id", "Naam", "Docentcode"})
_DROP_KEYS = frozenset({"Links", "Geboortedatum", "Email", "EmailAdres", "Telefoon"})

PERSON_ID_BASE = 1000
APPOINTMENT_ID_BASE = 100000
TEACHER_ID_BASE = 9000


def _letters(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA, ..."""
    letters = string.ascii_uppercase
    result = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        result = letters[rest] + result
    return result


class Anonymizer:
    """Stateful anonymizer: keeps ID/name mappings stable between calls."""

    def __init__(self, host: str | None = None) -> None:
        """Create an anonymizer; ``host`` is the real school host to scrub."""
        self._host = host.lower() if host else None
        self._person_ids: dict[int, int] = {}
        self._person_labels: dict[int, str] = {}
        self._appointment_ids: dict[int, int] = {}
        self._teachers: dict[str, int] = {}
        self._children = 0

    # ---------------------------------------------------------------- lookups

    def person_id(self, real: int) -> int:
        """Stable fake ID for a person."""
        if real not in self._person_ids:
            self._person_ids[real] = PERSON_ID_BASE + len(self._person_ids)
        return self._person_ids[real]

    def person_label(self, real: int, *, parent: bool = False) -> str:
        """Stable label: ``Ouder`` or ``Kind A``, ``Kind B``, ..."""
        if real not in self._person_labels:
            if parent:
                self._person_labels[real] = "Ouder"
            else:
                self._person_labels[real] = f"Kind {_letters(self._children)}"
                self._children += 1
        return self._person_labels[real]

    def appointment_id(self, real: int) -> int:
        """Stable fake ID for an appointment."""
        if real not in self._appointment_ids:
            self._appointment_ids[real] = APPOINTMENT_ID_BASE + len(
                self._appointment_ids
            )
        return self._appointment_ids[real]

    def teacher_number(self, key: str) -> int:
        """Stable number N for ``Docent N``."""
        if key not in self._teachers:
            self._teachers[key] = len(self._teachers) + 1
        return self._teachers[key]

    # ----------------------------------------------------------------- scrubbing

    def scrub_text(self, text: str) -> str:
        """Remove e-mail addresses, URLs and the school host from free text."""
        text = _URL_RE.sub(URL_PLACEHOLDER, text)
        text = _EMAIL_RE.sub(EMAIL_PLACEHOLDER, text)
        if self._host:
            text = re.sub(re.escape(self._host), SCHOOL_PLACEHOLDER, text, flags=re.I)
        return _MAGISTER_HOST_RE.sub(SCHOOL_PLACEHOLDER, text)

    # ----------------------------------------------------------------- payloads

    def account(self, data: dict[str, Any]) -> dict[str, Any]:
        """Anonymize an ``/api/account`` response."""
        groups = [g.get("Naam") for g in data.get("Groep") or [] if isinstance(g, dict)]
        persoon = data.get("Persoon")
        if isinstance(persoon, dict) and isinstance(persoon.get("Id"), int):
            self.person_label(persoon["Id"], parent="Ouder" in groups)
        result: dict[str, Any] = self._walk(data)
        return result

    def children(self, data: dict[str, Any]) -> dict[str, Any]:
        """Anonymize a ``/api/personen/<id>/kinderen`` response."""
        result: dict[str, Any] = self._walk(data)
        return result

    def appointments(self, data: dict[str, Any]) -> dict[str, Any]:
        """Anonymize an ``/api/personen/<id>/afspraken`` response."""
        result: dict[str, Any] = self._walk(data)
        return result

    # -------------------------------------------------------------------- walker

    def _walk(self, node: Any, key: str | None = None) -> Any:
        if isinstance(node, dict):
            if key == "Docenten" or _is_teacher(node):
                return self._teacher(node)
            if "Achternaam" in node or "Roepnaam" in node:
                return self._person(node)
            is_appointment = {"Start", "Einde", "Id"} <= node.keys()
            result: dict[str, Any] = {}
            for name, value in node.items():
                if name in _DROP_KEYS:
                    continue
                if name == "Bijlagen" and isinstance(value, list):
                    result[name] = [{"Naam": "bijlage"} for _ in value]
                elif (
                    name == "Id"
                    and is_appointment
                    and isinstance(value, int)
                    and not isinstance(value, bool)
                ):
                    result[name] = self.appointment_id(value)
                else:
                    result[name] = self._walk(value, name)
            return result
        if isinstance(node, list):
            return [self._walk(item, key) for item in node]
        if isinstance(node, str):
            return self.scrub_text(node)
        return node

    def _person(self, node: dict[str, Any]) -> dict[str, Any]:
        raw_id = node.get("Id")
        real = (
            raw_id if isinstance(raw_id, int) and not isinstance(raw_id, bool) else None
        )
        label = self.person_label(real) if real is not None else "Kind"
        out: dict[str, Any] = {}
        for name in _PERSON_KEYS & node.keys():
            if name == "Id":
                out[name] = self.person_id(real) if real is not None else raw_id
            elif name == "Roepnaam":
                out[name] = label
            elif name == "Voorletters":
                out[name] = label[0] + "."
            else:
                out[name] = ""
        return dict(sorted(out.items()))

    def _teacher(self, node: dict[str, Any]) -> dict[str, Any]:
        if "Naam" not in node and "Docentcode" not in node:
            return {k: self._walk(v, k) for k, v in node.items()}
        marker = str(node.get("Docentcode") or node.get("Naam") or node.get("Id"))
        number = self.teacher_number(marker)
        out: dict[str, Any] = {}
        for name in _TEACHER_KEYS & node.keys():
            if name == "Id":
                out[name] = TEACHER_ID_BASE + number
            elif name == "Naam":
                out[name] = f"Docent {number}"
            else:
                out[name] = f"D{number}"
        return dict(sorted(out.items()))


def _is_teacher(node: dict[str, Any]) -> bool:
    return "Docentcode" in node


def count_codes(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    """Count the values of an appointment field (``Status``, ``InfoType``, ``Type``)."""
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))

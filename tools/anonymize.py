"""Anonymize Magister API responses so they can be shared and committed.

Two passes over all payloads of one dump:

1. ``collect`` gathers every person name part (Roepnaam, Voorletters, Achternaam,
   Tussenvoegsel, Voornamen) and every teacher name and code, and assigns a
   placeholder (``Ouder``, ``Kind A``, ``Docent 1`` / ``D1``).
2. The ``account`` / ``children`` / ``appointments`` methods replace those values in
   ALL strings (case-insensitive, whole words, longest first), so a teacher code in
   ``Omschrijving`` ("wi - JDV - h4a") disappears too.

Also changed: person and appointment IDs become stable fake numbers; GUIDs and keys such
as ``UuId`` / ``ExterneId`` / ``OpdrachtId`` / ``Stamnummer`` are dropped or replaced;
``Naam`` of unknown list items becomes ``<naam>``; the school host becomes
``school.example``; e-mail addresses and URLs are removed from free text.

Review the output before sharing it: free text (``Omschrijving``, ``Inhoud``,
``Opmerking``) can still contain names that no tool can recognize.
"""

from __future__ import annotations

import re
import string
from typing import Any

SCHOOL_PLACEHOLDER = "school.example"
EMAIL_PLACEHOLDER = "email@example.invalid"
URL_PLACEHOLDER = "https://example.invalid/"
NAME_PLACEHOLDER = "<naam>"

_EMAIL_RE = re.compile(r"[\w.+'-]+@[\w-]+(?:\.[\w-]+)+")
_URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"')]+", re.IGNORECASE)
_MAGISTER_HOST_RE = re.compile(r"[\w-]+\.magister\.net", re.IGNORECASE)
_GUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE
)

_NAME_KEY_PARTS = ("naam", "voornam", "voorletter", "tussenvoegsel")


def _is_name_key(key: str) -> bool:
    """Person fields that hold (parts of) a name, e.g. OfficieleVoornamen."""
    lowered = key.lower()
    return any(part in lowered for part in _NAME_KEY_PARTS)


_PERSON_KEYS = frozenset(
    {"Id", "Roepnaam", "Tussenvoegsel", "Achternaam", "Voorletters"}
)
_TEACHER_KEYS = frozenset({"Id", "Naam", "Docentcode"})
_DROP_KEYS = frozenset(
    k.lower()
    for k in (
        "Links",
        "Geboortedatum",
        "Email",
        "EmailAdres",
        "Telefoon",
        "UuId",
        "Uuid",
        "ExterneId",
        "Stamnummer",
        "OpdrachtId",
    )
)
# Lists whose ``Naam`` is not personal.
_NAAM_KEEP_KEYS = frozenset({"Vakken", "Lokalen", "Groep", "Docenten", "Privileges"})
# Dutch name infixes: never replaced on their own (they are ordinary words).
_INFIXES = frozenset(
    {"de", "den", "der", "van", "von", "te", "ten", "ter", "het", "la", "le"}
)

PERSON_ID_BASE = 1000
APPOINTMENT_ID_BASE = 100000
TEACHER_ID_BASE = 9000


def _letters(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA, ..."""
    result = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        result = string.ascii_uppercase[rest] + result
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
        self._guids: dict[str, str] = {}
        self._children = 0
        self._replacements: dict[str, str] = {}
        self._pattern: re.Pattern[str] | None = None

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

    # -------------------------------------------------------------- pass 1

    def collect(self, data: Any) -> None:
        """Pass 1: register names and codes found in ``data`` for replacement."""
        if isinstance(data, dict) and "Persoon" in data and "Groep" in data:
            groups = [g.get("Naam") for g in data["Groep"] or [] if isinstance(g, dict)]
            persoon = data["Persoon"]
            if isinstance(persoon, dict) and _int_id(persoon) is not None:
                self.person_label(_int_id(persoon) or 0, parent="Ouder" in groups)
        self._collect(data)

    def _collect(self, node: Any, key: str | None = None) -> None:
        if isinstance(node, list):
            for item in node:
                self._collect(item, key)
        elif isinstance(node, dict):
            if "Docentcode" in node or (key == "Docenten" and "Naam" in node):
                self._collect_teacher(node)
            elif "Achternaam" in node or "Roepnaam" in node:
                self._collect_person(node)
            for name, value in node.items():
                self._collect(value, name)

    def _collect_teacher(self, node: dict[str, Any]) -> None:
        code = node.get("Docentcode")
        name = node.get("Naam")
        marker = str(code or name or node.get("Id"))
        number = self.teacher_number(marker)
        if isinstance(code, str):
            self._add(code, f"D{number}", min_len=2)
        if isinstance(name, str):
            self._add_name(name, f"Docent {number}")

    def _collect_person(self, node: dict[str, Any]) -> None:
        real = _int_id(node)
        label = self.person_label(real) if real is not None else "Kind"
        values = {
            k: v.strip()
            for k, v in node.items()
            if isinstance(v, str) and v.strip() and _is_name_key(k)
        }
        first = values.get("Roepnaam", "")
        last = values.get("Achternaam", "")
        infix = values.get("Tussenvoegsel", "")
        initials = values.get("Voorletters", "")
        first_names = values.get("Voornamen", "")
        for full in (
            " ".join(p for p in (first, infix, last) if p),
            " ".join(p for p in (initials, infix, last) if p),
            " ".join(p for p in (first_names, infix, last) if p),
        ):
            self._add(full, label)
        for key, value in values.items():
            exact = key in ("Roepnaam", "Achternaam")
            self._add(value, label, min_len=2 if exact else 3)
            for token in re.split(r"[\s,\-]+", value):
                self._add(token, label, min_len=2 if exact else 3)

    def _add_name(self, name: str, placeholder: str) -> None:
        self._add(name, placeholder)
        for token in re.split(r"[\s,\-]+", name):
            self._add(token, placeholder)

    def _add(self, value: str, placeholder: str, min_len: int = 3) -> None:
        value = value.strip()
        if len(value) < min_len or value.lower() in _INFIXES:
            return
        key = value.lower()
        if key not in self._replacements:
            self._replacements[key] = placeholder
            self._pattern = None

    # -------------------------------------------------------------- scrubbing

    def _name_pattern(self) -> re.Pattern[str] | None:
        if self._pattern is None and self._replacements:
            keys = sorted(self._replacements, key=len, reverse=True)
            self._pattern = re.compile(
                "|".join(rf"(?<!\w){re.escape(k)}(?!\w)" for k in keys), re.IGNORECASE
            )
        return self._pattern

    def scrub_text(self, text: str) -> str:
        """Pass 2 for one string: names, GUIDs, e-mail addresses, URLs, host."""
        text = _URL_RE.sub(URL_PLACEHOLDER, text)
        text = _EMAIL_RE.sub(EMAIL_PLACEHOLDER, text)
        text = _GUID_RE.sub(self._guid, text)
        if self._host:
            text = re.sub(re.escape(self._host), SCHOOL_PLACEHOLDER, text, flags=re.I)
        text = _MAGISTER_HOST_RE.sub(SCHOOL_PLACEHOLDER, text)
        if (pattern := self._name_pattern()) is not None:
            text = pattern.sub(lambda m: self._replacements[m.group(0).lower()], text)
        return text

    def _guid(self, match: re.Match[str]) -> str:
        key = match.group(0).lower()
        if key not in self._guids:
            self._guids[key] = f"00000000-0000-0000-0000-{len(self._guids) + 1:012d}"
        return self._guids[key]

    # ----------------------------------------------------------------- payloads

    def account(self, data: dict[str, Any]) -> dict[str, Any]:
        """Anonymize an ``/api/account`` response."""
        self.collect(data)
        result: dict[str, Any] = self._walk(data)
        return result

    def children(self, data: dict[str, Any]) -> dict[str, Any]:
        """Anonymize a ``/api/personen/<id>/kinderen`` response."""
        self.collect(data)
        result: dict[str, Any] = self._walk(data)
        return result

    def appointments(self, data: dict[str, Any]) -> dict[str, Any]:
        """Anonymize an ``/api/personen/<id>/afspraken`` response."""
        self.collect(data)
        result: dict[str, Any] = self._walk(data)
        return result

    # -------------------------------------------------------------------- walker

    def _walk(self, node: Any, key: str | None = None) -> Any:
        if isinstance(node, dict):
            if key == "Docenten" or "Docentcode" in node:
                return self._teacher(node)
            if "Achternaam" in node or "Roepnaam" in node:
                return self._person(node)
            is_appointment = {"Start", "Einde", "Id"} <= node.keys()
            result: dict[str, Any] = {}
            for name, value in node.items():
                if name.lower() in _DROP_KEYS:
                    continue
                if name == "Bijlagen" and isinstance(value, list):
                    result[name] = [{"Naam": "bijlage"} for _ in value]
                elif name == "Id" and is_appointment and _is_int(value):
                    result[name] = self.appointment_id(value)
                else:
                    result[name] = self._walk(value, name)
            return result
        if isinstance(node, list):
            items = [self._walk(item, key) for item in node]
            if key not in _NAAM_KEEP_KEYS:
                for item in items:
                    if isinstance(item, dict) and isinstance(item.get("Naam"), str):
                        item["Naam"] = NAME_PLACEHOLDER
            return items
        if isinstance(node, str):
            return self.scrub_text(node)
        return node

    def _person(self, node: dict[str, Any]) -> dict[str, Any]:
        real = _int_id(node)
        label = self.person_label(real) if real is not None else "Kind"
        out: dict[str, Any] = {}
        for name in _PERSON_KEYS & node.keys():
            if name == "Id":
                out[name] = self.person_id(real) if real is not None else node[name]
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


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _int_id(node: dict[str, Any]) -> int | None:
    value = node.get("Id")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def count_codes(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    """Count the values of an appointment field (``Status``, ``InfoType``, ``Type``)."""
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))

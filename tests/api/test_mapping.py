"""Tests for the appointment -> calendar field mapping."""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from custom_components.magister.api import Appointment, map_appointment
from custom_components.magister.api.mapping import build_summary, html_to_text

FIXTURES = Path(__file__).parent.parent / "fixtures"
SNAPSHOTS = Path(__file__).parent / "snapshots"
HOST = "school.magister.net"


def make(**overrides: Any) -> Appointment:
    """Build an appointment from a minimal JSON item."""
    item: dict[str, Any] = {
        "Id": 1,
        "Start": "2026-11-09T08:15:00.0000000Z",
        "Einde": "2026-11-09T09:00:00.0000000Z",
        "Omschrijving": "wi - D1 - k1a",
        "Vakken": [{"Naam": "wiskunde"}],
        "Status": 1,
        "InfoType": 0,
        "Type": 13,
    }
    item.update(overrides)
    return Appointment.from_json(item)


def snapshot_of(school: str) -> list[dict[str, Any]]:
    """Mapped fields of every fixture item as JSON-friendly dicts."""
    data = json.loads((FIXTURES / school / "appointments.json").read_text("utf-8"))
    result = []
    for item in data["Items"]:
        fields = map_appointment(Appointment.from_json(item), HOST)
        result.append(
            {
                "uid": fields.uid,
                "summary": fields.summary,
                "location": fields.location,
                "start": fields.start.isoformat(),
                "end": fields.end.isoformat(),
                "all_day": fields.all_day,
                "description": fields.description,
            }
        )
    return result


@pytest.mark.parametrize("school", ["school_a", "school_b"])
def test_fixture_snapshot(school: str) -> None:
    """Every fixture item maps to the reviewed snapshot.

    Set ``UPDATE_SNAPSHOTS=1`` to rewrite the snapshot after an intended change.
    """
    path = SNAPSHOTS / f"{school}.json"
    actual = snapshot_of(school)
    if os.environ.get("UPDATE_SNAPSHOTS"):  # pragma: no cover
        path.write_text(
            json.dumps(actual, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    assert actual == json.loads(path.read_text("utf-8"))


@pytest.mark.parametrize("school", ["school_a", "school_b"])
def test_fixture_invariants(school: str) -> None:
    """Properties that hold for every real item."""
    for fields in snapshot_of(school):
        assert fields["summary"].strip()
        assert fields["uid"].startswith("magister-")
        assert fields["uid"].endswith(f"@{HOST}")
        assert fields["start"] < fields["end"]
        assert "<" not in fields["description"]
        assert "&nbsp;" not in fields["description"]
        assert "\xa0" not in fields["description"]


def test_cancelled_with_homework() -> None:
    """Status 5 + homework: both prefixes, status line and homework text."""
    fields = map_appointment(
        make(
            Status=5,
            InfoType=1,
            Inhoud="<p>Maken opdracht 1</p>",
            LesuurVan=5,
            LesuurTotMet=5,
            Lokatie="017",
            Docenten=[{"Naam": "Docent 5"}],
        ),
        HOST,
    )
    assert fields.summary == "[Vervallen] [Huiswerk] wiskunde"
    assert fields.description == (
        "Lesuur 5\nVervallen\nwi - D1 - k1a\nDocent: Docent 5\n\nMaken opdracht 1"
    )
    assert fields.location == "017"
    assert fields.uid == f"magister-1@{HOST}"
    assert fields.start == datetime(2026, 11, 9, 8, 15, tzinfo=UTC)
    assert not fields.all_day


@pytest.mark.parametrize(
    ("status", "info_type", "prefix"),
    [
        (4, 0, "[Vervallen] "),
        (5, 0, "[Vervallen] "),
        (1, 1, "[Huiswerk] "),
        (1, 2, "[Proefwerk] "),
        (1, 3, "[Tentamen] "),
        (1, 4, "[SO] "),
        (1, 5, "[MO] "),
        (1, 6, "[Informatie] "),
        (1, 7, ""),
        (1, 99, ""),
        (3, 0, ""),
        (9, 0, ""),
        (10, 0, ""),
        (None, None, ""),
        (4, 2, "[Vervallen] [Proefwerk] "),
    ],
)
def test_prefixes(status: int | None, info_type: int | None, prefix: str) -> None:
    """Prefixes follow the PM-approved label words."""
    appointment = make(Status=status, InfoType=info_type)
    assert build_summary(appointment) == f"{prefix}wiskunde"


@pytest.mark.parametrize(
    ("status", "line"),
    [(3, "Gewijzigd"), (9, "Gewijzigd"), (10, "Verplaatst"), (4, "Vervallen")],
)
def test_status_lines(status: int, line: str) -> None:
    """Changed, moved and cancelled items get a status line."""
    description = map_appointment(make(Status=status), HOST).description
    assert description.splitlines()[0] == line


def test_multi_hour_and_empty_vakken_fall_back_to_omschrijving() -> None:
    """School B style: no Vakken, first Omschrijving segment, two lesson hours."""
    fields = map_appointment(
        make(
            Vakken=[],
            Omschrijving="wisB - K4wisB_1 - D1 - K4wisB_1",
            LesuurVan=4,
            LesuurTotMet=5,
            Lokalen=[{"Naam": "2.01"}, {"Naam": "2.02"}],
        ),
        HOST,
    )
    assert fields.summary == "wisB"
    assert fields.description.startswith("Lesuur 4\u20135\nwisB - K4wisB_1")
    assert fields.location == "2.01, 2.02"


def test_se_item_and_type_2_event() -> None:
    """``SE NAT`` is shown as is; a Type 2 school event has no prefix."""
    assert map_appointment(
        make(Vakken=[], Omschrijving="SE NAT - K4"), HOST
    ).summary == ("SE NAT")
    event = map_appointment(
        make(Vakken=[], Omschrijving="Schoolfotograaf - K4b", Type=2), HOST
    )
    assert event.summary == "Schoolfotograaf"


def test_everything_empty_uses_default_subject() -> None:
    """No Vakken and no Omschrijving: 'Afspraak', and nothing else to say."""
    fields = map_appointment(make(Vakken=[], Omschrijving=""), HOST)
    assert fields.summary == "Afspraak"
    assert fields.description == ""
    assert fields.location == ""


def test_attachments_line() -> None:
    """HeeftBijlagen adds a pointer to Magister."""
    fields = map_appointment(
        make(HeeftBijlagen=True, Inhoud="<p>zie bijlage</p>"), HOST
    )
    assert fields.description.endswith("zie bijlage\n\nBijlagen in Magister")


def test_period_variants() -> None:
    """Same start and end hour, no end hour, or no hour at all."""
    assert (
        "Lesuur 3\n"
        in map_appointment(make(LesuurVan=3, LesuurTotMet=3), HOST).description + "\n"
    )
    assert map_appointment(make(LesuurVan=3), HOST).description.startswith("Lesuur 3\n")
    assert not map_appointment(make(LesuurTotMet=3), HOST).description.startswith(
        "Lesuur"
    )


def test_teachers_plural() -> None:
    """Several teachers are listed under 'Docenten'."""
    description = map_appointment(
        make(Docenten=[{"Naam": "A"}, {"Naam": "B"}]), HOST
    ).description
    assert description.endswith("Docenten: A, B")


def test_all_day_event_is_date_only_with_exclusive_end() -> None:
    """Synthetic all-day item (not yet seen in real data)."""
    fields = map_appointment(
        make(
            Vakken=[],
            Omschrijving="Studiedag",
            DuurtHeleDag=True,
            Start="2026-11-09T23:00:00.0000000Z",  # 00:00 on 10 Nov in Amsterdam
            Einde="2026-11-10T23:00:00.0000000Z",  # 00:00 on 11 Nov
        ),
        HOST,
    )
    assert fields.all_day
    assert fields.start == date(2026, 11, 10)
    assert fields.end == date(2026, 11, 11)


def test_all_day_event_with_end_during_the_day_or_zero_length() -> None:
    """An end after midnight counts the end day; a zero-length item gets one day."""
    during = map_appointment(
        make(
            DuurtHeleDag=True,
            Start="2026-11-09T23:00:00.0000000Z",
            Einde="2026-11-11T11:00:00.0000000Z",
        ),
        HOST,
    )
    assert (during.start, during.end) == (date(2026, 11, 10), date(2026, 11, 12))
    zero = map_appointment(
        make(
            DuurtHeleDag=True,
            Start="2026-11-09T23:00:00.0000000Z",
            Einde="2026-11-09T23:00:00.0000000Z",
        ),
        HOST,
    )
    assert (zero.start, zero.end) == (date(2026, 11, 10), date(2026, 11, 11))


def test_zero_length_timed_event_gets_one_minute() -> None:
    """HA rejects events that end before they start."""
    fields = map_appointment(make(Einde="2026-11-09T08:15:00.0000000Z"), HOST)
    assert isinstance(fields.start, datetime)
    assert isinstance(fields.end, datetime)
    assert (fields.end - fields.start).total_seconds() == 60


@pytest.mark.parametrize(
    ("html", "text"),
    [
        ("", ""),
        ("plain", "plain"),
        ("<p>a</p><p>b</p>", "a\nb"),
        ("<p>a<br>b</p>", "a\nb"),
        ("a&nbsp;b &amp; c &gt; d", "a b & c > d"),
        ("<ul><li>een</li><li>twee</li></ul>", "- een\n- twee"),
        ("<ol><li>een <b>vet</b></li></ol>", "- een vet"),
        ("<p>a</p><p><br></p><p><br></p><p><br></p><p>b</p>", "a\n\nb"),
        ('<a href="https://example.invalid/x">link</a>', "link"),
        ("<style>p{}</style><script>x()</script>tekst", "tekst"),
        ("a<br/>b", "a\nb"),
        ("  veel   spaties \t hier ", "veel spaties hier"),
        ("<p>&nbsp;</p>", ""),
    ],
)
def test_html_to_text(html: str, text: str) -> None:
    """HTML is converted to readable plain text."""
    assert html_to_text(html) == text

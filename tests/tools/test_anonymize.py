"""Tests for the dump anonymizer."""

from __future__ import annotations

import json
from typing import Any

from tools.anonymize import Anonymizer, count_codes

HOST = "someschool.magister.net"

ACCOUNT = {
    "Persoon": {
        "Id": 4711,
        "Roepnaam": "Pieter",
        "Tussenvoegsel": "de",
        "Achternaam": "Echtnaam",
        "Voorletters": "P.",
        "Geboortedatum": "1975-01-01T00:00:00.0000000Z",
        "Email": "pieter@example.org",
    },
    "Groep": [{"Naam": "Ouder", "Id": 3}],
    "Links": {"self": {"href": f"https://{HOST}/api/account"}},
}

CHILDREN = {
    "Items": [
        {"Id": 501, "Roepnaam": "Anna", "Achternaam": "Echtnaam", "Voorletters": "A."},
        {
            "Id": 502,
            "Roepnaam": "Bram",
            "Achternaam": "Echtnaam",
            "Stamnummer": "123456",
        },
    ]
}


def appointment(app_id: int, teacher: str, code: str) -> dict[str, Any]:
    """A raw appointment."""
    return {
        "Id": app_id,
        "Start": "2026-11-09T07:30:00.0000000Z",
        "Einde": "2026-11-09T08:20:00.0000000Z",
        "Omschrijving": "wi - 1.01",
        "Vakken": [{"Id": 9, "Naam": "Wiskunde"}],
        "Docenten": [{"Id": 77, "Naam": teacher, "Docentcode": code}],
        "Lokalen": [{"Naam": "A101"}],
        "Inhoud": (
            f"Mail jan@school.nl of zie https://{HOST}/x?y=1 en www.voorbeeld.nl/pad,"
            f" of {HOST} zelf, of andere.magister.net"
        ),
        "Bijlagen": [{"Naam": "geheim.pdf", "Links": [{"href": "https://x"}]}],
        "Links": [{"href": f"https://{HOST}/api/x"}],
    }


def test_account_and_children_are_anonymized() -> None:
    """Names, IDs and personal fields are replaced; labels are stable."""
    anon = Anonymizer(HOST)
    account = anon.account(ACCOUNT)
    children = anon.children(CHILDREN)

    assert account["Persoon"] == {
        "Id": 1000,
        "Roepnaam": "Ouder",
        "Tussenvoegsel": "",
        "Achternaam": "",
        "Voorletters": "O.",
    }
    assert "Links" not in account
    assert children["Items"][0] == {
        "Id": 1001,
        "Roepnaam": "Kind A",
        "Achternaam": "",
        "Voorletters": "K.",
    }
    assert children["Items"][1]["Roepnaam"] == "Kind B"
    assert "Stamnummer" not in children["Items"][1]
    dumped = json.dumps([account, children])
    for secret in ("Pieter", "Echtnaam", "Anna", "Bram", "4711", "pieter@", "1975"):
        assert secret not in dumped
    assert anon.person_label(501) == "Kind A"
    assert anon.person_id(501) == 1001


def test_student_account_gets_child_label() -> None:
    """A non-parent account holder is labeled as a child."""
    anon = Anonymizer(HOST)
    out = anon.account(
        {"Persoon": {"Id": 5, "Roepnaam": "Sam"}, "Groep": [{"Naam": "Leerling"}]}
    )
    assert out["Persoon"]["Roepnaam"] == "Kind A"


def test_appointments_are_anonymized_and_stable() -> None:
    """IDs, teachers and free text are scrubbed consistently across calls."""
    anon = Anonymizer(HOST)
    first = anon.appointments({"Items": [appointment(31337, "J. Jansen", "JAN")]})
    second = anon.appointments(
        {
            "Items": [
                appointment(31337, "J. Jansen", "JAN"),
                appointment(42, "K. Klaassen", "KLA"),
            ]
        }
    )
    item = first["Items"][0]
    assert item["Id"] == 100000
    assert second["Items"][0]["Id"] == 100000
    assert second["Items"][1]["Id"] == 100001
    assert item["Docenten"] == [{"Id": 9001, "Naam": "Docent 1", "Docentcode": "D1"}]
    assert second["Items"][1]["Docenten"][0]["Naam"] == "Docent 2"
    assert item["Vakken"] == [{"Id": 9, "Naam": "Wiskunde"}]
    assert item["Lokalen"] == [{"Naam": "A101"}]
    assert item["Bijlagen"] == [{"Naam": "bijlage"}]
    assert "Links" not in item

    text = item["Inhoud"]
    assert text.startswith("Mail email@example.invalid of zie https://example.invalid/")
    for leaked in ("jan@", HOST, "voorbeeld", "andere.magister", "geheim", "Jansen"):
        assert leaked not in json.dumps(first)
    assert "school.example" in text


def test_teacher_without_code_or_name_and_odd_values() -> None:
    """Unusual shapes do not crash."""
    anon = Anonymizer()
    out = anon.appointments(
        {
            "Items": [
                {
                    "Id": True,
                    "Start": "x",
                    "Einde": "y",
                    "Docenten": [{"Id": 1}],
                    "Getal": 5,
                    "Leeg": None,
                    "Persoon": {"Roepnaam": "Zonder Id"},
                }
            ]
        }
    )
    item = out["Items"][0]
    assert item["Docenten"] == [{"Id": 1}]
    assert item["Id"] is True
    assert item["Persoon"]["Roepnaam"] == "Kind"
    assert item["Getal"] == 5


def test_many_children_get_distinct_labels() -> None:
    """Labels continue after Z."""
    anon = Anonymizer()
    labels = [anon.person_label(i) for i in range(28)]
    assert labels[0] == "Kind A"
    assert labels[25] == "Kind Z"
    assert labels[26] == "Kind AA"
    assert len(set(labels)) == 28


def test_count_codes() -> None:
    """Codes are counted as strings, sorted."""
    items = [{"Status": 1}, {"Status": 5}, {"Status": 1}, {}]
    assert count_codes(items, "Status") == {"1": 2, "5": 1, "None": 1}

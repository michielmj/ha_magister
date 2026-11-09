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


# ------------------------------------------------------------ review fixes (M1)


def realistic_payload() -> dict[str, Any]:
    """A payload shaped like a real afspraken response."""
    return {
        "Items": [
            {
                "Id": 91,
                "Start": "2026-11-09T07:30:00.0000000Z",
                "Einde": "2026-11-09T08:20:00.0000000Z",
                "Omschrijving": "wi - JDV - h4a",
                "Lokatie": "A101 (mevr. Jansen)",
                "Lokalen": [{"Naam": "A101"}],
                "Vakken": [{"Id": 2, "Naam": "Wiskunde", "UuId": "x"}],
                "Docenten": [
                    {"Id": 5, "Naam": "J. de Vries", "Docentcode": "JDV"},
                    {"Id": 6, "Naam": "M. Jansen"},
                ],
                "Inhoud": "Vraag het aan jdv of aan Mevr. DE VRIES; Anna levert in",
                "UuId": "5b0b1d9a-2a8e-4c1f-9b53-0d9c3b6f7e11",
                "ExterneId": "ext-1",
                "OpdrachtId": 77,
                "Opmerking": "Zie 5B0B1D9A-2A8E-4C1F-9B53-0D9C3B6F7E11",
                "Groepen": [{"Naam": "Brugklas Annaschool"}],
                "Aantekeningen": [{"Naam": "Bram Echtnaam", "Tekst": "x"}],
            }
        ]
    }


def test_teacher_codes_and_names_replaced_everywhere() -> None:
    """Codes/names from Docenten disappear from all other strings."""
    anon = Anonymizer(HOST)
    item = anon.appointments(realistic_payload())["Items"][0]
    assert item["Omschrijving"] == "wi - D1 - h4a"
    assert item["Lokatie"] == "A101 (mevr. Docent 2)"
    assert item["Docenten"][0] == {"Id": 9001, "Naam": "Docent 1", "Docentcode": "D1"}
    text = item["Inhoud"]
    assert "jdv" not in text.lower()
    assert "vries" not in text.lower()
    assert text.startswith("Vraag het aan D1 of aan Mevr.")
    assert "Docent 1" in text


def test_person_names_replaced_in_free_text_across_payloads() -> None:
    """Names from account/children are scrubbed in appointments too."""
    anon = Anonymizer(HOST)
    anon.collect(ACCOUNT)
    anon.collect(CHILDREN)
    item = anon.appointments(realistic_payload())["Items"][0]
    assert "Anna" not in item["Inhoud"]
    assert "Kind A" in item["Inhoud"]
    assert "Echtnaam" not in json.dumps(item)
    # ordinary words equal to a name infix are not touched
    assert anon.scrub_text("maak de som van het getal") == "maak de som van het getal"
    # whole words only
    assert anon.scrub_text("Annabel") == "Annabel"


def test_ids_guids_and_external_keys_are_dropped() -> None:
    """UuId, ExterneId, OpdrachtId and GUIDs anywhere are gone."""
    anon = Anonymizer(HOST)
    item = anon.appointments(realistic_payload())["Items"][0]
    for key in ("UuId", "ExterneId", "OpdrachtId"):
        assert key not in item
    assert "UuId" not in item["Vakken"][0]
    assert "5b0b1d9a" not in json.dumps(item).lower()
    assert item["Opmerking"] == "Zie 00000000-0000-0000-0000-000000000001"


def test_naam_in_unknown_lists_is_replaced() -> None:
    """Naam is kept for Vakken/Lokalen/Groep but replaced elsewhere."""
    anon = Anonymizer(HOST)
    item = anon.appointments(realistic_payload())["Items"][0]
    assert item["Vakken"][0]["Naam"] == "Wiskunde"
    assert item["Lokalen"] == [{"Naam": "A101"}]
    assert item["Groepen"] == [{"Naam": "<naam>"}]
    assert item["Aantekeningen"][0]["Naam"] == "<naam>"
    account = anon.account(ACCOUNT)
    assert account["Groep"][0]["Naam"] == "Ouder"


# ------------------------------------------------------------ final round


def test_official_and_birth_name_fields_and_hyphen_parts() -> None:
    """All *naam* person fields are collected and split on spaces and hyphens."""
    anon = Anonymizer(HOST)
    anon.collect(
        {
            "Persoon": {
                "Id": 1,
                "Roepnaam": "Hendrika",
                "Achternaam": "Ouder-Jansen",
                "OfficieleVoornamen": "Hendrika Johanna",
                "OfficieleTussenvoegsels": "van den",
                "OfficieleAchternaam": "Jansen",
                "GeboorteAchternaam": "Pietersen",
                "GeboortenaamTussenvoegsel": "de",
            },
            "Groep": [{"Naam": "Ouder"}],
        }
    )
    text = anon.scrub_text(
        "tante Johanna, Hendrika ziek, mevr. Ouder-Jansen, Pietersen"
    )
    for leaked in ("Johanna", "Hendrika", "Jansen", "Pietersen"):
        assert leaked not in text
    assert "Ouder" in text


def test_two_letter_first_and_last_names_are_replaced() -> None:
    """Exact Roepnaam/Achternaam values of 2 letters are replaced as whole words."""
    anon = Anonymizer(HOST)
    anon.collect({"Items": [{"Id": 3, "Roepnaam": "Bo", "Achternaam": "Li"}]})
    assert anon.scrub_text("Bo komt, Bob niet, en li ook") == (
        "Kind A komt, Bob niet, en Kind A ook"
    )
    anon2 = Anonymizer(HOST)
    anon2.collect({"Items": [{"Id": 4, "Roepnaam": "Ab", "Voornamen": "Cd Ef"}]})
    # the full Voornamen value is replaced; its 2-letter parts alone are not
    assert anon2.scrub_text("Ab Cd Ef / Cd") == "Kind A Kind A / Cd"


def test_privileges_names_are_kept() -> None:
    """Groep[].Privileges[].Naam is not blanked."""
    anon = Anonymizer(HOST)
    out = anon.account(
        {
            "Persoon": {"Id": 1, "Roepnaam": "X"},
            "Groep": [{"Naam": "Ouder", "Privileges": [{"Naam": "Agenda", "X": 1}]}],
        }
    )
    assert out["Groep"][0]["Privileges"][0]["Naam"] == "Agenda"

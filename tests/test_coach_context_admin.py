"""M13: clearing context outside the AI, store, children, diagnostics."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.core import Context, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers.storage import Store

from custom_components.magister.const import CONF_CHILDREN, DOMAIN
from custom_components.magister.context import SERVICE_CLEAR_COACH_CONTEXT
from custom_components.magister.diagnostics import async_get_config_entry_diagnostics
from custom_components.magister.homework import STORE_MINOR_VERSION, _HomeworkStore

from .ha_helpers import NOW, FakeMagister, make_entry
from .test_coach import HOMEWORK, coach_options, make_user, ok, setup_coach

SECRET = "geheimnotitie-voor-ouders"


@pytest.fixture(autouse=True)
async def frozen_now(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> FrozenDateTimeFactory:
    """Friday 13 November 2026."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(NOW)
    return freezer


class Setup:
    """An entry with two children and a parent of both."""

    entry: Any
    parent: Any


@pytest.fixture
async def two(hass: HomeAssistant, mocked: aioresponses) -> Setup:
    """Two children; notes are added by the tests."""
    result = Setup()
    result.parent = await make_user(hass, "Ouder")
    result.entry = await setup_coach(
        hass,
        mocked,
        coach_options(
            **{
                "1001": {"enabled": True, "parents": [result.parent.id]},
                "1002": {"enabled": True, "parents": [result.parent.id]},
            }
        ),
        two=True,
    )
    return result


async def fill(hass: HomeAssistant, setup: Setup) -> None:
    """Notes for both children, in two subjects."""
    uid = setup.parent.id
    for child in ("1001", "1002"):
        await ok(hass, uid, "add_context", child=child, scope="child", text="Algemeen")
        await ok(
            hass,
            uid,
            "add_context",
            child=child,
            scope="subject",
            subject="wiskunde",
            text="Boek",
        )
    await ok(
        hass,
        uid,
        "add_context",
        child="1001",
        scope="item",
        item=HOMEWORK,
        text="Blz 3",
        visibility="parents",
    )
    await ok(
        hass,
        uid,
        "add_context",
        child="1001",
        scope="subject",
        subject="Duitse taal",
        text="Woordjes",
    )


# -- options flow ----------------------------------------------------------------------


async def start_clear(hass: HomeAssistant, entry: Any) -> Any:
    """Configure > AI coach > Context wissen."""
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "coach"}
    )
    assert "coach_context" in result["menu_options"]
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "coach_context"}
    )


async def test_clear_subject_through_the_options_flow(
    hass: HomeAssistant, two: Setup
) -> None:
    """Child, then one subject (only subjects with notes), then the confirmation."""
    await fill(hass, two)
    book = two.entry.runtime_data.homework.context
    result = await start_clear(hass, two.entry)
    assert result["step_id"] == "coach_context"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"child": "1001"}
    )
    assert result["step_id"] == "coach_context_scope"
    assert result["description_placeholders"] == {"child": "Anna A"}
    options = next(iter(result["data_schema"].schema.values())).config["options"]
    assert [o["value"] for o in options] == ["Duitse taal", "wiskunde"]
    # A subject without notes is not accepted (the form stays open).
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"], {"subject": "Latijn"}
        )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"subject": "wiskunde"}
    )
    assert result["step_id"] == "coach_context_confirm"
    # wiskunde: the subject note and the (parents-only) item note of the lesson.
    assert result["description_placeholders"] == {
        "child": "Anna A",
        "count": "2",
        "subject": "wiskunde",
    }
    assert book.count(1001) == 4  # nothing is deleted before the confirmation
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "context_cleared"
    assert result["description_placeholders"] == {"count": "2"}
    assert book.count(1001) == 2
    assert book.subjects_with_notes(1001) == ["Duitse taal"]
    assert book.count(1002) == 2  # the other child is untouched


async def test_clear_all_through_the_options_flow(
    hass: HomeAssistant, two: Setup
) -> None:
    """Leaving the subject empty deletes all context of the child."""
    await fill(hass, two)
    book = two.entry.runtime_data.homework.context
    result = await start_clear(hass, two.entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"child": "1002"}
    )
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["step_id"] == "coach_context_confirm"
    assert result["description_placeholders"]["count"] == "2"
    assert result["description_placeholders"]["subject"] == "\u2013"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["reason"] == "context_cleared"
    assert book.count(1002) == 0
    assert book.count(1001) == 4


async def test_clear_flow_without_notes_and_with_one_child(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """One child skips the choice; no notes ends the flow with a message."""
    user = await make_user(hass, "Ouder")
    entry = await setup_coach(
        hass,
        mocked,
        coach_options(**{"1001": {"enabled": True, "parents": [user.id]}}),
    )
    result = await start_clear(hass, entry)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_context"
    await ok(hass, user.id, "add_context", scope="child", text="Hoi")
    result = await start_clear(hass, entry)
    assert result["step_id"] == "coach_context_scope"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["reason"] == "context_cleared"
    assert entry.runtime_data.homework.context.count(1001) == 0


# -- the service -----------------------------------------------------------------------


async def clear_service(
    hass: HomeAssistant, data: dict[str, Any], user: Any = None
) -> Any:
    """Call the service with a response, as a user (none: automation)."""
    return await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR_COACH_CONTEXT,
        data,
        blocking=True,
        return_response=True,
        context=Context(user_id=user.id if user else None),
    )


async def test_service_clears_and_returns_the_number(
    hass: HomeAssistant, two: Setup
) -> None:
    """A subject or the whole child; the response has the number deleted."""
    await fill(hass, two)
    book = two.entry.runtime_data.homework.context
    entry_id = two.entry.entry_id
    result = await clear_service(
        hass, {"config_entry_id": entry_id, "child": "1001", "subject": "WISKUNDE"}
    )
    assert result == {"deleted": 2}
    assert book.count(1001) == 2
    assert await clear_service(
        hass, {"config_entry_id": entry_id, "child": "1001", "subject": "wiskunde"}
    ) == {"deleted": 0}
    # By name; no subject: everything of that child only.
    assert await clear_service(
        hass, {"config_entry_id": entry_id, "child": "anna"}
    ) == {"deleted": 2}
    assert book.count(1001) == 0
    assert book.count(1002) == 2
    assert await clear_service(
        hass, {"config_entry_id": entry_id, "child": "Bram B", "subject": " "}
    ) == {"deleted": 2}
    # Without asking for the response it just works.
    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR_COACH_CONTEXT,
        {"config_entry_id": entry_id, "child": 1002},
        blocking=True,
    )


async def test_service_checks(hass: HomeAssistant, two: Setup) -> None:
    """Administrators only; the entry and the child must exist."""
    await fill(hass, two)
    entry_id = two.entry.entry_id
    book = two.entry.runtime_data.homework.context
    data = {"config_entry_id": entry_id, "child": "1001"}
    # (The first user of a test instance is its owner: use another one.)
    plain = await make_user(hass, "Gewoon")
    with pytest.raises(Unauthorized):
        await clear_service(hass, data, plain)
    assert book.count(1001) == 4
    admin = await hass.auth.async_create_user("Beheer", group_ids=[GROUP_ID_ADMIN])
    assert (await clear_service(hass, data, admin)) == {"deleted": 4}
    for bad in (
        {"config_entry_id": "nope", "child": "1001"},
        {"config_entry_id": entry_id, "child": "9999"},
    ):
        with pytest.raises(ServiceValidationError):
            await clear_service(hass, bad)
    # A name that two children share is not guessed.
    ambiguous = {"config_entry_id": entry_id, "child": "1001"}
    children = [dict(c) for c in two.entry.data[CONF_CHILDREN]]
    children[1]["short_name"] = children[0]["short_name"]
    hass.config_entries.async_update_entry(
        two.entry, data={**two.entry.data, CONF_CHILDREN: children}
    )
    with pytest.raises(ServiceValidationError) as raised:
        await clear_service(
            hass, {**ambiguous, "child": str(children[0]["short_name"]).upper()}
        )
    assert raised.value.translation_key == "child_ambiguous"
    # An entry of another integration is not accepted.
    other = make_entry(unique_id="x:1")
    other.add_to_hass(hass)
    with pytest.raises(ServiceValidationError):
        await clear_service(hass, {"config_entry_id": other.entry_id, "child": "1001"})
    # An entry that is not loaded is not either.
    assert await hass.config_entries.async_unload(entry_id)
    with pytest.raises(ServiceValidationError):
        await clear_service(hass, data)


async def test_service_is_described() -> None:
    """The service has a services.yaml entry and translations (NL and EN)."""
    from pathlib import Path

    base = Path(__file__).parents[1] / "custom_components" / "magister"
    assert "clear_coach_context:" in (base / "services.yaml").read_text()
    for name in ("strings.json", "translations/en.json", "translations/nl.json"):
        data = json.loads((base / name).read_text())
        service = data["services"]["clear_coach_context"]
        assert set(service["fields"]) == {"config_entry_id", "child", "subject"}
        assert data["exceptions"]["child_not_found"]["message"]
        assert data["exceptions"]["child_ambiguous"]["message"]
        assert data["exceptions"]["entry_not_loaded"]["message"]
        step = data["options"]["step"]
        assert step["coach"]["menu_options"]["coach_context"]
        assert {"coach_context", "coach_context_scope", "coach_context_confirm"} <= set(
            step
        )
        assert {"no_context", "context_cleared"} <= set(data["options"]["abort"])


# -- children and entries --------------------------------------------------------------


async def test_removing_a_child_removes_its_context(
    hass: HomeAssistant, two: Setup, hass_storage: dict[str, Any]
) -> None:
    """The notes of an unselected child are gone after the reload."""
    await fill(hass, two)
    entry = two.entry
    key = f"{DOMAIN}.homework.{entry.entry_id}"
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_CHILDREN: entry.data[CONF_CHILDREN][:1]}
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    book = entry.runtime_data.homework.context
    assert book.count(1001) == 4
    assert book.count(1002) == 0
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert set(hass_storage[key]["data"]["context"]) == {"1001"}


async def test_removing_the_entry_removes_the_store(
    hass: HomeAssistant, two: Setup, hass_storage: dict[str, Any]
) -> None:
    """Deleting the config entry deletes the store with the notes."""
    await fill(hass, two)
    key = f"{DOMAIN}.homework.{two.entry.entry_id}"
    assert await hass.config_entries.async_unload(two.entry.entry_id)
    assert hass_storage[key]["data"]["context"]
    assert await hass.config_entries.async_remove(two.entry.entry_id)
    assert key not in hass_storage


# -- the store -------------------------------------------------------------------------


def stored_note(**fields: Any) -> dict[str, Any]:
    """A note as stored."""
    return {
        "id": "aaaa0001",
        "scope": "child",
        "text": "Opgeslagen",
        "visibility": "all",
        "created_by": "parent",
        "updated": "2026-11-12",
        **fields,
    }


async def test_store_1_6_file_has_no_context_and_is_saved_as_1_8(
    hass: HomeAssistant, mocked: aioresponses, hass_storage: dict[str, Any]
) -> None:
    """A 1.7.x file loads unchanged; notes are saved under the new key."""
    entry = make_entry(options=coach_options(**{"1001": {"enabled": True}}))
    key = f"{DOMAIN}.homework.{entry.entry_id}"
    hass_storage[key] = {
        "version": 1,
        "minor_version": 6,
        "key": key,
        "data": {"items": {}},
    }
    FakeMagister(mocked)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = entry.runtime_data.homework
    book = manager.context
    assert book.count(1001) == 0
    book.add(1001, parent=True, scope="child", text="Nieuw")
    assert await hass.config_entries.async_unload(entry.entry_id)
    saved = hass_storage[key]
    assert (saved["version"], saved["minor_version"]) == (1, STORE_MINOR_VERSION)
    assert STORE_MINOR_VERSION == 9
    assert [n["text"] for n in saved["data"]["context"]["1001"]] == ["Nieuw"]
    # No notes: no key (a clean file).
    book.clear(1001)
    assert "context" not in manager._data()


async def test_store_read_by_the_previous_release(
    hass: HomeAssistant, mocked: aioresponses, hass_storage: dict[str, Any]
) -> None:
    """Downgrade: a release with minor 6 loads the 1.7 file and finds its items."""
    entry = make_entry(options=coach_options(**{"1001": {"enabled": True}}))
    key = f"{DOMAIN}.homework.{entry.entry_id}"
    FakeMagister(mocked)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = entry.runtime_data.homework
    manager.set_progress(f"school.magister.net:1001:{HOMEWORK}", 50)
    manager.context.add(1001, parent=True, scope="child", text="Nieuw")
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass_storage[key]["minor_version"] == 9
    # 1.7.x: the same class of store at minor version 6, same major version.
    old = _HomeworkStore(hass, 1, key, minor_version=6)
    data = await old.async_load()
    assert data is not None
    assert data["items"]
    assert "context" in data  # ignored by 1.7.x (it reads only `items`)
    # Plain `Store` with the same major version loads it too (no data is refused).
    plain = Store[dict[str, Any]](hass, 1, key, minor_version=6)
    assert (await plain.async_load()) is not None


async def test_store_with_damaged_context_is_read_leniently(
    hass: HomeAssistant, mocked: aioresponses, hass_storage: dict[str, Any]
) -> None:
    """Invalid notes, duplicate ids, unknown children and wrong types are dropped."""
    entry = make_entry(options=coach_options(**{"1001": {"enabled": True}}))
    key = f"{DOMAIN}.homework.{entry.entry_id}"
    hass_storage[key] = {
        "version": 1,
        "minor_version": 7,
        "key": key,
        "data": {
            "items": {},
            "context": {
                "1001": [
                    stored_note(),
                    stored_note(text="dubbel"),  # same id
                    stored_note(id="aaaa0002", scope="nope"),
                    stored_note(id="n5"),  # not an 8-hex id: dropped
                    stored_note(id="AAAA0005"),  # upper case: dropped
                    "kapot",
                    stored_note(id="aaaa0003", text=SECRET, visibility="parents"),
                    stored_note(
                        id="aaaa0004",
                        scope="period",
                        start="2026-11-16",
                        end="2026-11-17",
                        daily_max_minutes=30,
                    ),
                ],
                "9999": [
                    stored_note(id="bbbb0001")
                ],  # a child that is not in the entry
                "abc": [stored_note(id="bbbb0002")],
                "1002": "geen lijst",
            },
        },
    }
    FakeMagister(mocked)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    book = entry.runtime_data.homework.context
    assert [n.id for n in book.all_notes(1001)] == ["aaaa0001", "aaaa0003", "aaaa0004"]
    assert book.count(9999) == 0
    # (Ids that are not 8 lowercase hex characters are dropped, not renumbered.)
    assert book.daily_max_overrides(1001) == {"2026-11-16": 30, "2026-11-17": 30}
    # Garbage at the top level is ignored as well.
    book.load("niets", date(2026, 11, 13))
    assert book.all_notes(1001) == []


async def test_store_load_ignores_a_missing_or_wrong_file(
    hass: HomeAssistant, mocked: aioresponses, hass_storage: dict[str, Any]
) -> None:
    """No store, or a context that is not a mapping: an empty book."""
    entry = make_entry(options=coach_options(**{"1001": {"enabled": True}}))
    key = f"{DOMAIN}.homework.{entry.entry_id}"
    hass_storage[key] = {
        "version": 1,
        "minor_version": 7,
        "key": key,
        "data": {"items": {}, "context": [1, 2]},
    }
    FakeMagister(mocked)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.homework.context.count(1001) == 0


# -- diagnostics -----------------------------------------------------------------------


async def test_diagnostics_have_counts_only(hass: HomeAssistant, two: Setup) -> None:
    """Notes per scope and the parents-only count; no text, subject or id."""
    await fill(hass, two)
    await ok(
        hass,
        two.parent.id,
        "add_context",
        child="1002",
        scope="period",
        start="2026-11-16",
        end="2026-11-16",
        text=SECRET,
        visibility="parents",
    )
    data = await async_get_config_entry_diagnostics(hass, two.entry)
    assert data["coach_context"] == {
        "notes": {"child": 2, "subject": 3, "item": 1, "period": 1},
        "parents_only": 2,
    }
    text = json.dumps(data, default=str)
    for secret in (SECRET, "Opgeslagen", "wiskunde", "Duitse taal", "Woordjes", "Boek"):
        assert secret not in text
    assert "aaaa0001" not in data["coach_context"]

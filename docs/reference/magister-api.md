# Magister data API (as used by this integration)

Base URL: `https://<school>.magister.net`, header `Authorization: Bearer <access_token>`,
`Accept: application/json`. Timestamps are UTC with 7 fractional digits
(`2026-11-09T07:30:00.0000000Z`); requests use `YYYY-MM-DDTHH:MM:SS.000Z`.

Status of this document: structure from `docs/reference/magister_agenda.py`; codes
confirmed from the anonymized dump of school A (M1) where marked **confirmed**, otherwise
community-reported and unconfirmed. `tools/magister_cli.py --dump` writes
`observed-codes.json` to extend this for other schools.

## Endpoints

| Call | Response (relevant fields) |
|---|---|
| `GET /api/account` | `Persoon{Id, Roepnaam, Tussenvoegsel, Achternaam, Voorletters}`, `Groep[{Naam}]` (`"Ouder"` for parent accounts) |
| `GET /api/personen/{ouderId}/kinderen` | `Items[]` with the same person fields |
| `GET /api/personen/{persoonId}/afspraken?van=<UTC>&tot=<UTC>[&status=1]` | `Items[]` of appointments; **do not send `status=1`** (hides cancelled lessons) |

Behaviour of the client (`api/client.py`): 401 -> one forced token refresh and retry, a
second 401 -> `MagisterApiError(status=401)` (the coordinator turns it into `UpdateFailed`); 429 -> `MagisterApiError(status=429)`;
5xx and network errors/timeouts (30 s) -> `MagisterConnectionError`; other statuses ->
`MagisterApiError(status)`.

## Appointment fields

| JSON | Model field | Notes |
|---|---|---|
| `Id` | `id` | |
| `Start`, `Einde` | `start`, `end` | UTC-aware datetimes |
| `DuurtHeleDag` | `all_day` | end is exclusive/next midnight (to be confirmed) |
| `Omschrijving` | `description` | |
| `Vakken[].Naam` | `subjects` | |
| `Lokatie`, `Lokalen[].Naam` | `location`, `classrooms` | `location` falls back to the rooms |
| `Docenten[].Naam` | `teachers` | |
| `LesuurVan`, `LesuurTotMet` | `period_start`, `period_end` | |
| `Inhoud` | `content` | HTML (homework / test text) |
| `Status` | `status` (int) | see below |
| `InfoType` | `info_type` (int) | see below |
| `Type` | `type` (int) | see below |
| `Afgerond` | `afgerond` | homework done |

Unknown or non-integer codes are kept (`int`) or turned into `None`; they never raise.

## Codes

Legend: **confirmed** = observed in real data (school A, one child, 140 appointments from
one week back to three weeks ahead; fixtures in `tests/fixtures/school_a/`);
**community** = reported by community libraries, not yet observed here.

### `status=1` query parameter: it hides cancelled lessons (confirmed)

With `status=1` the API returned 130 items, without it 140. The 10 extra items are
**exactly the items with `Status` 5**. So `status=1` removes cancelled lessons, and the
integration **must fetch without the status filter** (`MagisterClient.async_get_appointments`
defaults to `status=None` since M1) to be able to show `[Vervallen]` items.

### `Status`

Status 4 and 5 get the prefix `[Vervallen]` (HLD section 7).

| Code | Observed count | Meaning |
|---|---|---|
| 1 | 72 (**confirmed** present) | normal scheduled item (shown by `status=1`) |
| 3 | 10 (**confirmed** present) | shown by `status=1`; seen at school A; Magister shows it as a normal lesson (no changed marker; the "Bijgewerkt op ..." text appears on every appointment); meaning unknown; the integration adds no note to the description; mostly natuurkunde (8 of 10, also 1x du, 1x en); all are lessons |
| 5 | 10 (**confirmed** present) | **cancelled** (hidden by `status=1`); all 10 are lessons |
| 7 | 48 (**confirmed** present) | shown by `status=1`; exact meaning not determined |
| 0, 2, 4, 6, 8+ | not observed | community, unconfirmed (4 is expected to be a second "cancelled" variant, manual vs. automatic) |

Observed date pattern (**unconfirmed hypothesis**): Status 7 occurs only on dates up to the
dump date (2026-11-02..2026-11-13), possibly meaning "closed / past"; Status 1 occurs on
2026-11-03..2026-11-30 and Status 3 on 2026-11-12..2026-11-30.

The CLI marks Status 4 and 5 as `[VERVALLEN]`. Meanings of 1/3/7 beyond "not cancelled" are
open; none of the observed items had `Afgerond` set.

### `InfoType`

| Code | Observed count (school A) | Meaning | Prefix per HLD section 7 |
|---|---|---|---|
| 0 | 87 (**confirmed**) | none | |
| 1 | 47 (**confirmed**) | homework | `[Huiswerk]` |
| 2 | 2 (**confirmed**) | test (proefwerk) | `[Proefwerk]` |
| 3 | not observed | exam (tentamen), community, unconfirmed | `[Tentamen]` |
| 4 | 4 (**confirmed**) | written quiz (schriftelijke overhoring), e.g. "Schriftcontrole", "s.o." | `[SO]` |
| 5 | not observed | oral quiz (mondelinge overhoring), community, unconfirmed | `[MO]` |
| 6 | not observed | information, community, unconfirmed | `[Informatie]` |
| 7 | not observed | note, community, unconfirmed | |

Note: the 10 cancelled (Status 5) items include 3 with InfoType 1 (homework on a cancelled
lesson).

### `Type`

| Code | Observed count | Meaning |
|---|---|---|
| 13 | 136 (**confirmed**) | lesson |
| 7 | 4 (**confirmed** present) | observed for an "NT2" item; likely KWT / keuzewerktijd (choice hour) |
| 1 | not observed | personal appointment, community, unconfirmed |
| 2 | school A: not observed; school B: 2 (**confirmed**) | general; e.g. "Schoolfotograaf", "Voorlichting PTA en PTD" |
| 3 | not observed | school-wide, community, unconfirmed |
| 4 | not observed | internship, community, unconfirmed |
| 5 | not observed | intake, community, unconfirmed |
| 6 | not observed | free period, community, unconfirmed |
| 16 | not observed | planning, community, unconfirmed |

### Other observations

* Timestamps have 7 fractional digits and `Z` (`2026-11-02T08:15:00.0000000Z`).
* No item had `DuurtHeleDag` true, so all-day behaviour is still unconfirmed.
* `Omschrijving` of lessons looks like `<subject code> - <teacher code(s)> - <class code>`.
* Each item also has `Subtype`, `IsOnlineDeelname`, `WeergaveType`, `HerhaalStatus`,
  `Herhaling`, `Groepen[{Code}]`, `HeeftBijlagen`, `Bijlagen`, `Opmerking` and
  `Aantekening`. In school A `HeeftBijlagen` was always false; at school B it was true on 3
  items (text says "zie bijlage") while `Bijlagen` stayed null. `Bijlagen`, `Opmerking`
  and `Aantekening` were always null at both schools; `Subtype`, `IsOnlineDeelname`,
  `WeergaveType`, `HerhaalStatus` and `Herhaling` were constant. None are modelled.

### School B observations (second school, 94 items / 89 with `status=1`)

Fixtures: `tests/fixtures/school_b/`.

* **`Vakken` is empty for every item.** The subject is only available as the first
  `" - "` segment of `Omschrijving` (`wisB`, `SE NAT`, `Schoolfotograaf`). Omschrijving
  here looks like `<subject> - <group(s)> - <teacher code(s)> - <group(s)>`, and can
  contain things like `10 docenten - 10 groepen` or `26 leerlingen`.
  `Appointment.subject` therefore falls back to that first segment when `Vakken` is
  empty and keeps the `Vakken` name when present.
* **Status 5 = cancelled is confirmed at a second school:** `status=1` hides exactly the
  5 Status 5 items. Other codes: Status 1 (36), 7 (53); InfoType 0, 1, 2; Type 13 and 2.
* **Type 2 is confirmed in data** (general items such as a school photographer and an
  information evening, not lessons).
* **`SE <VAK>` items are school exams** (e.g. `SE NAT`, `SE WISB`) and have InfoType 0,
  so they are not recognizable as tests via InfoType; the `SE ` prefix is the only hint.
* **Multi-hour items exist** (`LesuurVan` 4, `LesuurTotMet` 5, up to 3 hours).
* **A teacher's text can signal a cancellation the status does not show:** one Status 1
  lesson has Inhoud "les gaat niet door ivm ...". The integration only marks Status 4/5
  as cancelled; this text is shown as normal homework/description.
* No item had `DuurtHeleDag` true. `HeeftBijlagen` was **true on 3 items** (100002,
  100015, 100032; their text says "zie bijlage") while `Bijlagen` stayed null, so the
  attachment list is not returned by this endpoint. `Opmerking` and `Aantekening` were
  always null.

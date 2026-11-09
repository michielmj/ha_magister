# Magister data API (as used by this integration)

Base URL: `https://<school>.magister.net`, header `Authorization: Bearer <access_token>`,
`Accept: application/json`. Timestamps are UTC with 7 fractional digits
(`2026-11-09T07:30:00.0000000Z`); requests use `YYYY-MM-DDTHH:MM:SS.000Z`.

Status of this document: structure taken from `docs/reference/magister_agenda.py` and the
community libraries. **Everything marked "unconfirmed" must be confirmed from the PM's
anonymized dumps** (`tools/magister_cli.py --dump`), which also writes
`observed-codes.json` with counts per code, with and without the `status=1` filter.

## Endpoints

| Call | Response (relevant fields) |
|---|---|
| `GET /api/account` | `Persoon{Id, Roepnaam, Tussenvoegsel, Achternaam, Voorletters}`, `Groep[{Naam}]` (`"Ouder"` for parent accounts) |
| `GET /api/personen/{ouderId}/kinderen` | `Items[]` with the same person fields |
| `GET /api/personen/{persoonId}/afspraken?status=1&van=<UTC>&tot=<UTC>` | `Items[]` of appointments |

Behaviour of the client (`api/client.py`): 401 -> one forced token refresh and retry, a
second 401 -> `MagisterAuthError(invalid_auth)`; 429 -> `MagisterApiError(status=429)`;
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

### `InfoType` (community-reported, **unconfirmed**)

| Code | Meaning | Prefix per HLD section 7 |
|---|---|---|
| 0 | none | |
| 1 | homework | `[HW]` |
| 2 | test (proefwerk) | `[Toets]` |
| 3 | exam (tentamen) | `[Toets]` |
| 4 | written quiz (schriftelijke overhoring) | `[SO]` |
| 5 | oral quiz (mondelinge overhoring) | `[MO]` |
| 6 | information | |
| 7 | note | |

### `Type` (community-reported, **unconfirmed**)

| Code | Meaning |
|---|---|
| 1 | personal appointment |
| 2 | general |
| 3 | school-wide |
| 4 | internship |
| 5 | intake |
| 6 | free period / free |
| 7 | KWT (choice hour) |
| 13 | lesson |
| 16 | planning |

### `Status` (**not recorded**; to be derived from the dumps)

No reliable list is known to the developer. Community sources suggest several codes for
"scheduled", "changed", "moved" and "cancelled" (manual and automatic variants). The
dump tool counts the observed values; the table will be filled in after the PM shares the
dumps. Open questions for that:

1. which `Status` values mean cancelled (`[Vervallen]`) and which mean changed/moved;
2. whether the `status=1` query parameter hides cancelled lessons (compare
   `appointments-<kind>.json` with `appointments-<kind>-without-status-filter.json`).

`MagisterClient.async_get_appointments(..., status=1)` keeps the reference script's
default; pass `status=None` to omit the parameter if it turns out to hide cancelled
lessons.

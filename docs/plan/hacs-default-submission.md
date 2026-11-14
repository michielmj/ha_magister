# Submitting to the HACS default store

Status (2026-11-14): **not submitted yet**. The PM decided to submit after 1.4.0 is released.

Source: the `hacs/default` repository (README, `.github/PULL_REQUEST_TEMPLATE.md`, `.github/workflows/checks.yml`,
`scripts/check/*`), read on 2026-11-14. The guides at https://hacs.xyz/docs/publish/start and
https://hacs.xyz/docs/publish/include are the authoritative text; read them before submitting.

## Automatic checks HACS runs on the submission PR
| Check | How this repository meets it |
|---|---|
| Releases: at least one GitHub release | Releases since v1.2.0 (publish v1.4.0 first) |
| HACS action (`hacs/action`, category integration) **without** an `ignore` key | `.github/workflows/hacs.yml` has no `ignore`; green |
| Hassfest | `.github/workflows/hassfest.yml`; green |
| Core domain conflict: `magister` must not be a core HA domain | Not in HA 2026.10.4 |
| Owner: the PR author is the repository owner or a major contributor | The PM (`michielmj`) submits |
| Existing/removed: not already in HACS | Not listed |
| Editable PR: "Allow edits by maintainers" enabled | Tick it when opening the PR (needs a fork in a personal account, not an organisation) |
| The `integration` list stays sorted (case-insensitive) | Insert the line in alphabetical order |

## Steps for the PM
1. Make sure the latest release (v1.4.0) is published, and that the **HACS** and **Hassfest** workflow runs for that
   commit on `main` are green. Note the links to:
   - the release: `https://github.com/michielmj/ha_magister/releases/tag/v1.4.0`;
   - a green HACS action run: Actions → HACS → the run for the release commit;
   - a green Hassfest run: Actions → Hassfest → the same commit.
2. On GitHub, open https://github.com/hacs/default and click **Fork** (into your personal account).
3. In your fork, open the file **`integration`** and click the pencil (Edit).
4. Add the line `"michielmj/ha_magister",` at its **alphabetical** place (case-insensitive; between the entries just
   before and after "michielmj/…"). Keep the JSON valid: quotes and a comma, and no comma after the last entry.
5. Commit to a new branch, then **Create pull request** to `hacs/default` (`master`).
   - Fill in the checklist from the template and tick each box (all are met; see the table above).
   - Under **Links**, paste the three links from step 1.
   - Make sure **"Allow edits by maintainers"** is ticked.
   - Do **not** request reviews (the template says this gets the PR closed).
6. Wait. The checks run automatically, and a HACS maintainer reviews in their own time (weeks are normal). Answer
   questions on the PR; the Architect can help with any requested changes in this repository.
7. After the merge: the integration appears in HACS's store for everyone. Existing installs from the custom repository
   keep working. You can remove the custom-repository entry in your own HACS after the default entry shows up.

## Notes
- Keep the HACS and Hassfest workflows green, and keep publishing releases. The store follows releases.
- Do not rename the repository or the domain after inclusion.

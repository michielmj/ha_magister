# M4 — Release 1.0

| | |
|---|---|
| Status | **Draft — awaiting PM approval** |
| Branch | `claude/jolly-mayer-i2h3oo` |
| Refs | Implementation plan (M4) · HLD §8–§9 |

## Goal

Turn the working integration (0.3.1, accepted on HAOS) into a **1.0 release** that other parents
can install and use without help: clear documentation in Dutch and English, a proper release
process for HACS, a project icon, issue templates that protect privacy, and a final full audit.

## Out of scope

New features (backlog: passkey login, homework/test sensors, change events, grades/absences,
on-demand fetch outside the window, publishing `api/` to PyPI). Submission to the HACS default store
(see open point 2).

## Tasks

### 1. User documentation (README.md in English + README.nl.md in Dutch, linked to each other)
- What it does: calendars per child, labels, first-appointment sensors. Include a screenshot-free
  description, or anonymized screenshots only.
- Requirements: Home Assistant 2026.10.4+, a Magister account with username + password
  (SSO/passkey-only accounts are not supported), optional TOTP secret: where to find it and that
  re-pairing the authenticator may be needed.
- Installation: install HACS first (link to the official guide); add the custom repository with
  type **Integration**, install, restart, and refresh the browser. Also the manual installation.
- Setup: one entry per Magister login (several logins per school are fine), choosing children,
  options (window, interval), first-appointment sensors (offset, exclusions), the automation
  examples (Time trigger with an offset, choosing the today/tomorrow sensor, a fallback for alarms).
- How it behaves: refresh every 30 min, stays available on last data for up to 24 h,
  cancelled lessons, labels, title fallback, the meaning of "unknown".
- Troubleshooting: the re-login card, "login blocked" and how a reload helps, the repair messages,
  where to find logs, how to download diagnostics. **Never post names, screenshots with names, or
  passwords in issues.**
- Privacy & security: what is stored (credentials in HA's config entry), what is never logged,
  the lockout protection, data only goes to Magister.
- Disclaimer: unofficial, not affiliated with Iddink/Magister, it may break when Magister changes
  its login.

### 2. Project icon
A **generic** school/calendar icon (no Magister logo or name styling: trademark and impersonation risk).
Ship it in the way HA 2026.10 supports for custom integrations (verify: a local `brand/` folder in
the integration, or a PR to home-assistant/brands). Remove `ignore: brands` from the HACS
workflow once it passes.

### 3. Release process
- `.github/workflows/release.yml`: on a pushed tag `v*.*.*`, verify that the tag matches the manifest
  version, run the tests, and create a GitHub release with the notes from the matching CHANGELOG section.
- `hacs.json`: keep `render_readme`; add `zip_release` only if needed (not required).
- Document the release steps in `docs/plan/release.md`: bump the version in the manifest, pyproject
  and user agent → CHANGELOG → PR → merge → tag. The Architect pushes the tag; the workflow publishes.

### 4. Repository hygiene
- `.github/ISSUE_TEMPLATE/`: a bug report (HA version, integration version, diagnostics file attached,
  explicit privacy warning) and a feature request. `SECURITY.md` (how to report privately).
- Dependabot for GitHub Actions and the pip test requirements (weekly).
- Bump the actions to their current majors (checkout, setup-python) if CI shows warnings.
- `tools/magister_cli.py` stays as a troubleshooting tool, documented in a short section of the README.

### 5. Version 1.0.0
Manifest, pyproject, user agent and CHANGELOG ("1.0.0: first stable release", summarizing 0.1–0.3).

### 6. Final audit (Reviewer, fresh session)
A full-repository review, not a diff: security (secrets, logging, lockout paths), privacy (fixtures,
docs, history of `main`), HA quality-scale style checks (config flow, translations, diagnostics,
reauth, unique ids, entity naming), the README's accuracy against the behaviour, and the test suite's health.
Findings are fixed before tagging.

## Acceptance criteria
- [ ] All tasks done; audit findings resolved; CI green (including HACS without `ignore: brands`, if the icon route allows it).
- [ ] **PM review of the README (NL + EN):** clear for another parent?
- [ ] **PM:** after the merge, the Architect pushes tag `v1.0.0`; the release appears on GitHub; HACS on HAOS
      offers 1.0.0 as an update; install it and the calendars and sensors keep working.

## Open points for the PM
1. **Repository visibility:** HACS can only install for other people if the repository is **public**.
   Is it public, or should it become public at 1.0?
2. **HACS default store:** submit to HACS's default repository list after 1.0, so others can
   find it without adding a custom repository? This is a separate review process by the HACS maintainers.
   Proposed: not now; decide after 1.0 has run for a while.
3. **Name and attribution in the docs:** use your GitHub handle as maintainer (as in the manifest's
   codeowners)? No real names will be used.

# Release process

Releases are installed by HACS from GitHub releases. The tag `vX.Y.Z` must equal `v` plus the
`version` in `custom_components/magister/manifest.json`; the workflow `.github/workflows/release.yml`
checks this, runs the tests and publishes the release with the notes from the matching
`## X.Y.Z` section of `CHANGELOG.md`.

## Steps

1. Branch from `main`. Bump the version in three places:
   - `custom_components/magister/manifest.json` (`version`)
   - `pyproject.toml` (`version`)
   - `custom_components/magister/api/auth.py` (`USER_AGENT`)
2. In `CHANGELOG.md` turn the notes under `## Unreleased` into a `## X.Y.Z` section (the heading
   is exactly `## X.Y.Z`, nothing after the version) and leave an empty `## Unreleased` above it.
3. Run the checks locally: `ruff check .`, `ruff format --check .`, `mypy`,
   `pytest --cov=custom_components.magister`. Run the privacy grep from the maintainer's private notes (it is not listed here).
4. Open a PR, wait for CI (Tests, Hassfest, HACS), merge it.
5. The Architect pushes the tag on the merge commit:
   `git tag vX.Y.Z && git push origin vX.Y.Z`.
6. The Release workflow publishes the GitHub release. Check it on GitHub, then in HACS (on a
   test installation: Redownload/Update) that X.Y.Z is offered and installs.

## If the workflow fails

Fix the cause on `main`, delete the tag locally and on the remote
(`git push origin :refs/tags/vX.Y.Z`), and push the tag again on the new commit. Never move a
tag that already has a published release; bump to the next patch version instead.

## Notes

- Dependabot ignores `pytest-homeassistant-custom-component`: the Home Assistant baseline
  (that package, `homeassistant` in `hacs.json` and the README requirement) is bumped by hand.
- HACS shows the README (`render_readme`) and the release notes from the GitHub release.
- The icon is shipped in `custom_components/magister/brand/` (HA 2026.10 serves it for custom
  integrations); the source is `docs/assets/icon.svg`.
- The repository is public at 1.0. Submission to the HACS default store is not planned; revisit
  after 1.0 has run for a while.

## Note: creating the tag
The cloud development session cannot push tags. The maintainer creates the release in the GitHub UI:
Releases → Draft a new release → tag `vX.Y.Z` on `main` (create on publish) → title `X.Y.Z` → notes from
CHANGELOG → Publish. The release workflow then runs on the new tag (tests, version check) and fills in the same release.

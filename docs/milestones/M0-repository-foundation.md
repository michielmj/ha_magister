# M0 — Repository foundation

| | |
|---|---|
| Status | **Accepted by PM (2026-11-09)** — reviewed and approved; CI green except HACS topics (repo setting) |
| Branch | `claude/jolly-mayer-i2h3oo` |
| Refs | `docs/design/high-level-design.md` §4, §9 · `docs/plan/implementation-plan.md` |

## Goal

A repository skeleton for a HACS custom integration `magister`. The integration
**loads in Home Assistant but does nothing yet**, and all quality gates (tests, ruff,
hassfest, HACS validation) run in GitHub Actions. Later milestones only add code.

## Out of scope

Any Magister API, auth, config flow logic, coordinator or calendar code (M1/M2).
Do not add `pyotp` or other runtime requirements yet.

## Tasks

1. **Integration stub** in `custom_components/magister/`:
   - `manifest.json`: `domain: magister`, `name: Magister`, `codeowners: ["@michielmj"]`,
     `config_flow: false` (switched on in M2), `documentation` and `issue_tracker`
     pointing to `https://github.com/michielmj/ha_magister`, `iot_class: cloud_polling`,
     `integration_type: service`, `requirements: []`, `version: 0.0.1`.
     Key order must follow hassfest rules (domain, name, then alphabetical).
   - `const.py` with `DOMAIN = "magister"`.
   - `__init__.py`: `CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)`, and
     `async_setup` returning `True`. Also add `async_setup_entry` / `async_unload_entry`
     stubs that return `True`, so the layout matches the HLD.
   - Fully typed and passing ruff. No blocking I/O.
2. **HACS:** `hacs.json` with `name`, `homeassistant` (the minimum HA version
   matching the pinned test package), `render_readme: true`.
3. **Python tooling:**
   - `pyproject.toml`: project metadata (no packaging needed), ruff config (target the
     Python version HA currently requires; rule sets at least `E, F, W, I, UP, B, ASYNC,
     SIM, RUF`), ruff format, pytest config (`asyncio_mode = "auto"`, `testpaths = ["tests"]`),
     mypy config (strict for `custom_components/magister/api/` later; for now basic
     settings that pass).
   - `requirements_test.txt`: pin `pytest-homeassistant-custom-component` to its
     latest release on PyPI (check under Python 3.14; `pip index` hides releases that need a newer interpreter) (this pins HA itself), plus `ruff`, `mypy`, `aioresponses`,
     `pytest-cov`. Pin exact versions.
   - `.gitignore` for Python/venv/caches/coverage/HA config dirs.
4. **Tests** in `tests/`:
   - `conftest.py` with an autouse fixture enabling custom integrations
     (`enable_custom_integrations`).
   - `test_init.py`: `async_setup_component(hass, DOMAIN, {})` succeeds, and
     `async_setup_entry` / `async_unload_entry` called directly with a `MockConfigEntry`
     return `True`. *(Spec change after review: a full config-entry lifecycle test is not
     possible without a config flow. It moves to M2. No patching of HA internals.)*
5. **GitHub Actions** in `.github/workflows/`, triggered on `push` and `pull_request`:
   - `tests.yml`: set up Python, install `requirements_test.txt`, `ruff check`,
     `ruff format --check`, `pytest --cov=custom_components.magister`.
   - `hassfest.yml`: `home-assistant/actions/hassfest@master`.
   - `hacs.yml`: `hacs/action@main` with `category: integration` and `ignore: brands`
     (brand assets are a later concern).
6. **Docs/meta:** `LICENSE` (MIT, copyright holder `michielmj`), `README.md` stub
   (one paragraph on what the integration will do, status "under development",
   HACS custom-repository install placeholder, link to `docs/`), `CHANGELOG.md` with an
   "Unreleased" section.

## Acceptance criteria

- [ ] `ruff check .` and `ruff format --check .` are clean locally.
- [ ] `pytest` passes locally, with the tests above.
- [ ] All three workflows exist and use pinned or official action references.
- [ ] After push, the `tests` and `hassfest` workflows are green on the branch. The HACS
      action may only fail on repository-settings checks (description/topics), which the
      PM fixes in GitHub settings. Any such failure is reported, not worked around.
- [ ] No secrets, personal data or Magister data in the repo.
- [ ] Commits on `claude/jolly-mayer-i2h3oo` with clear messages.

## PM actions (outside the code)

- If HACS validation asks for it: set a repository description and topics
  (e.g. `home-assistant`, `hacs`, `magister`) in GitHub settings.

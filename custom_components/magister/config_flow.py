"""Config flow for Magister."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import probatio
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    Account,
    MagisterApiError,
    MagisterAuth,
    MagisterAuthError,
    MagisterClient,
    MagisterConnectionError,
    MagisterLoginPageError,
    Person,
    normalize_host,
)
from .api.errors import (
    AUTH_INVALID,
    AUTH_INVALID_TOTP,
    AUTH_TOTP_REQUIRED,
    AUTH_UNSUPPORTED_LOGIN,
)
from .const import (
    CONF_CHILDREN,
    CONF_HOST,
    CONF_REMOVE_TOTP,
    CONF_SCHOOL,
    CONF_TOTP_SECRET,
    DOMAIN,
    SUBENTRY_FIRST,
    host_prefix,
)
from .options_flow import MagisterOptionsFlow, child_entry, children_in_other_entries
from .pending import PendingLogin, store_pending_login
from .subentry_flow import FirstAppointmentSubentryFlow

_LOGGER = logging.getLogger(__name__)

_AUTH_ERRORS = frozenset(
    {AUTH_INVALID, AUTH_TOTP_REQUIRED, AUTH_INVALID_TOTP, AUTH_UNSUPPORTED_LOGIN}
)

USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_SCHOOL): TextSelector(),
        probatio.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT, autocomplete="username")
        ),
        probatio.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD, autocomplete="current-password"
            )
        ),
        probatio.Optional(CONF_TOTP_SECRET): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


def _credentials_schema(*, reauth: bool) -> probatio.Schema:
    """Form of the reauth (password) and reconfigure (username, password) steps."""
    fields: dict[Any, Any] = {}
    if not reauth:
        fields[probatio.Required(CONF_USERNAME)] = TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT, autocomplete="username")
        )
    password_marker = probatio.Required if reauth else probatio.Optional
    fields[password_marker(CONF_PASSWORD)] = TextSelector(
        TextSelectorConfig(
            type=TextSelectorType.PASSWORD, autocomplete="current-password"
        )
    )
    fields[probatio.Optional(CONF_TOTP_SECRET)] = TextSelector(
        TextSelectorConfig(type=TextSelectorType.PASSWORD)
    )
    if not reauth:
        fields[probatio.Optional(CONF_REMOVE_TOTP, default=False)] = BooleanSelector()
    return probatio.Schema(fields)


class MagisterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a Magister login (one school account)."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> MagisterOptionsFlow:
        """Return the options flow (children, window, refresh interval)."""
        return MagisterOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """First-appointment sensors are sub-entries."""
        return {SUBENTRY_FIRST: FirstAppointmentSubentryFlow}

    def __init__(self) -> None:
        """Initialise the flow."""
        self._login: PendingLogin | None = None
        self._handed_over = False
        self._user_input: dict[str, Any] = {}
        self._host = ""
        self._account: Account | None = None
        self._children: list[Person] = []

    # ------------------------------------------------------------ steps

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the school and the credentials, and validate them."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                host = normalize_host(user_input[CONF_SCHOOL])
            except ValueError:
                errors[CONF_SCHOOL] = "invalid_school"
            else:
                error = await self._async_validate(host, user_input)
                if error is None:
                    return await self._async_after_login(host, user_input)
                errors["base"] = error
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    def _taken_children(self) -> set[int]:
        """Children of this school that another login already has."""
        return children_in_other_entries(self.hass, self._host, None)

    async def async_step_children(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the parent pick the children that get a calendar."""
        errors: dict[str, str] = {}
        if user_input is not None:
            selected = {int(value) for value in user_input[CONF_CHILDREN]}
            chosen = [child for child in self._children if child.id in selected]
            if not chosen:
                errors["base"] = "no_children_selected"
            elif {child.id for child in chosen} & self._taken_children():
                errors["base"] = "child_already_configured"
            else:
                return self._async_create_entry(chosen)

        options = [
            SelectOptionDict(value=str(child.id), label=child.name)
            for child in self._children
            if child.id not in self._taken_children()
        ]
        schema = probatio.Schema(
            {
                probatio.Required(
                    CONF_CHILDREN, default=[option["value"] for option in options]
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="children", data_schema=schema, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start the re-login after the credentials stopped working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the new password (and optionally a new authenticator secret)."""
        return await self._async_credentials_step("reauth_confirm", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the username, password or authenticator secret of the account."""
        return await self._async_credentials_step("reconfigure", user_input)

    async def _async_credentials_step(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Validate new credentials with exactly one login and hand it over."""
        reauth = self.source == SOURCE_REAUTH
        entry = self._get_reauth_entry() if reauth else self._get_reconfigure_entry()
        host: str = entry.data[CONF_HOST]
        errors: dict[str, str] = {}
        if user_input is not None:
            remove_totp = bool(user_input.get(CONF_REMOVE_TOTP))
            credentials = {
                CONF_USERNAME: entry.data[CONF_USERNAME]
                if reauth
                else user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input.get(CONF_PASSWORD)
                or entry.data[CONF_PASSWORD],
                CONF_TOTP_SECRET: None
                if remove_totp
                else user_input.get(CONF_TOTP_SECRET)
                or entry.data.get(CONF_TOTP_SECRET),
            }
            error = await self._async_validate(host, credentials, with_children=False)
            if error is None:
                assert self._account is not None
                try:
                    await self.async_set_unique_id(
                        f"{host}:{self._account.person.id}", raise_on_progress=False
                    )
                    self._abort_if_unique_id_mismatch(reason="wrong_account")
                except AbortFlow:
                    self._discard_login()
                    raise
                return self._async_hand_over(entry, host, credentials)
            errors["base"] = error
        schema = _credentials_schema(reauth=reauth)
        suggested = {CONF_USERNAME: entry.data[CONF_USERNAME]}
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or suggested
            ),
            errors=errors,
            description_placeholders={
                "school": host_prefix(host),
                "username": entry.data[CONF_USERNAME],
            },
        )

    def _async_hand_over(
        self, entry: ConfigEntry, host: str, credentials: dict[str, Any]
    ) -> ConfigFlowResult:
        """Give the validated login to the entry so the reload does not log in."""
        assert self._login is not None
        assert entry.unique_id is not None
        totp = credentials[CONF_TOTP_SECRET]
        totp_secret = totp.replace(" ", "") if totp else None
        self._login.credentials = (
            host,
            credentials[CONF_USERNAME],
            credentials[CONF_PASSWORD],
            totp_secret,
        )
        store_pending_login(self.hass, entry.unique_id, self._login)
        self._handed_over = True
        data = {
            CONF_USERNAME: credentials[CONF_USERNAME],
            CONF_PASSWORD: credentials[CONF_PASSWORD],
        }
        if totp_secret:
            data[CONF_TOTP_SECRET] = totp_secret
        new_data = {k: v for k, v in entry.data.items() if k != CONF_TOTP_SECRET}
        new_data |= data
        result = self.async_update_and_abort(entry, data=new_data)
        self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return result

    # ---------------------------------------------------------- helpers

    def _discard_login(self) -> None:
        """Release the HA-managed session (``close()`` is forbidden for those)."""
        if self._login is not None:
            self._login.session.detach()
            self._login = None

    @callback
    def async_remove(self) -> None:
        """Release the session of a login that was never used."""
        if self._login is not None and not self._handed_over:
            self._discard_login()

    async def _async_validate(
        self, host: str, user_input: dict[str, Any], *, with_children: bool = True
    ) -> str | None:
        """Log in and read the account (and children); return an error key."""
        self._discard_login()
        # Own cookie jar: the login session cookies must not be shared.
        session = async_create_clientsession(self.hass, auto_cleanup=False)
        auth = MagisterAuth(
            session,
            host,
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
            user_input.get(CONF_TOTP_SECRET) or None,
        )
        client = MagisterClient(session, auth, host)
        self._login = PendingLogin(session=session, auth=auth, client=client)
        try:
            account = await client.async_get_account()
            children = (
                await client.async_get_children(account.person.id)
                if account.is_parent and with_children
                else [account.person]
            )
        except MagisterAuthError as err:
            _LOGGER.debug(
                "Login to %s failed: %s (server error: %s)",
                host,
                err.code,
                err.server_error,
            )
            self._discard_login()
            return err.code if err.code in _AUTH_ERRORS else AUTH_INVALID
        except MagisterConnectionError as err:
            _LOGGER.debug("Could not connect to %s: %s", host, err)
            self._discard_login()
            return "cannot_connect"
        except MagisterLoginPageError as err:
            _LOGGER.debug("The login page of %s changed: %s", host, err)
            self._discard_login()
            return "login_page_changed"
        except MagisterApiError as err:
            _LOGGER.debug("Unexpected answer from %s: %s", host, err)
            self._discard_login()
            return "cannot_connect" if err.status == 429 else "unknown"
        except Exception:
            _LOGGER.exception("Unexpected exception during login to %s", host)
            self._discard_login()
            return "unknown"
        self._account = account
        self._children = children
        return None

    async def _async_after_login(
        self, host: str, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        assert self._account is not None
        self._host = host
        self._user_input = user_input
        try:
            await self.async_set_unique_id(f"{host}:{self._account.person.id}")
            self._abort_if_unique_id_configured()
        except AbortFlow:
            self._discard_login()
            raise
        if not self._children:
            self._discard_login()
            return self.async_abort(reason="no_children")
        if all(child.id in self._taken_children() for child in self._children):
            self._discard_login()
            return self.async_abort(reason="all_children_configured")
        if not self._account.is_parent:
            return self._async_create_entry(self._children)
        return await self.async_step_children()

    def _async_create_entry(self, children: list[Person]) -> ConfigFlowResult:
        assert self._account is not None
        assert self._login is not None
        assert self.unique_id is not None
        data: dict[str, Any] = {
            CONF_HOST: self._host,
            CONF_USERNAME: self._user_input[CONF_USERNAME],
            CONF_PASSWORD: self._user_input[CONF_PASSWORD],
            CONF_CHILDREN: [child_entry(child) for child in children],
        }
        if totp_secret := self._user_input.get(CONF_TOTP_SECRET):
            data[CONF_TOTP_SECRET] = totp_secret.replace(" ", "")
        store_pending_login(self.hass, self.unique_id, self._login)
        self._handed_over = True
        name = self._account.person.first_name or self._account.person.name
        return self.async_create_entry(
            title=f"Magister {host_prefix(self._host)} ({name})", data=data
        )

"""Config flow for Emaldo integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EmaldoAPIClient, EmaldoAuthError, EmaldoConnectionError
from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class EmaldoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Emaldo."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = EmaldoAPIClient(
                session, user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )

            try:
                await client.login()
                homes = await client.get_homes()
            except EmaldoAuthError:
                errors["base"] = "invalid_auth"
            except EmaldoConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                if not homes:
                    errors["base"] = "no_homes"
                else:
                    await self.async_set_unique_id(user_input[CONF_EMAIL])
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=f"Emaldo ({user_input[CONF_EMAIL]})",
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

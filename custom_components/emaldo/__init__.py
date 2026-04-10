"""The Emaldo integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EmaldoAPIClient
from .const import CONF_EMAIL, CONF_PASSWORD
from .coordinator import EmaldoCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

type EmaldoConfigEntry = ConfigEntry[list[EmaldoCoordinator]]


async def async_setup_entry(hass: HomeAssistant, entry: EmaldoConfigEntry) -> bool:
    """Set up Emaldo from a config entry."""
    session = async_get_clientsession(hass)
    client = EmaldoAPIClient(
        session, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD]
    )

    await client.login()
    homes = await client.get_homes()

    coordinators: list[EmaldoCoordinator] = []

    for home in homes:
        home_id = home["home_id"]
        devices = await client.get_devices(home_id)

        for device in devices:
            # Establish E2E real-time connection
            await client.e2e_connect(home_id, device)

            coordinator = EmaldoCoordinator(
                hass,
                client,
                home_id=home_id,
                device_id=device["id"],
                device_model=device["model"],
                device_name=device.get("name", device["model"]),
            )
            await coordinator.async_config_entry_first_refresh()
            await coordinator.start_heartbeat()
            coordinators.append(coordinator)

    entry.runtime_data = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EmaldoConfigEntry) -> bool:
    """Unload a config entry."""
    for coordinator in entry.runtime_data:
        await coordinator.async_shutdown()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

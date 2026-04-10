"""Data update coordinator for Emaldo."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EmaldoAPIClient, EmaldoAuthError, EmaldoConnectionError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class EmaldoCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch data from Emaldo API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: EmaldoAPIClient,
        home_id: str,
        device_id: str,
        device_model: str,
        device_name: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.home_id = home_id
        self.device_id = device_id
        self.device_model = device_model
        self.device_name = device_name

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.client.get_current_data(
                self.home_id, self.device_id, self.device_model
            )
        except EmaldoAuthError:
            _LOGGER.debug("Token expired, re-authenticating")
            try:
                await self.client.login()
                return await self.client.get_current_data(
                    self.home_id, self.device_id, self.device_model
                )
            except EmaldoAuthError as err:
                raise UpdateFailed(f"Authentication failed: {err}") from err
        except EmaldoConnectionError as err:
            raise UpdateFailed(f"Connection error: {err}") from err

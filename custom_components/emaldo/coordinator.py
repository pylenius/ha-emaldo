"""Data update coordinator for Emaldo."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EmaldoAPIClient, EmaldoAuthError, EmaldoConnectionError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class EmaldoCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that polls Emaldo via E2E every N seconds."""

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
        self._heartbeat_task: asyncio.Task | None = None

    async def start_heartbeat(self) -> None:
        """Start periodic heartbeat to keep E2E connection alive."""
        if self._heartbeat_task is not None:
            return
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self) -> None:
        """Send alive + heartbeat every 15 seconds to keep session alive."""
        fail_count = 0
        try:
            while True:
                await asyncio.sleep(15)
                if not self.client._e2e_connected:
                    _LOGGER.debug("Heartbeat loop: disconnected, exiting")
                    return
                # Send both alive and heartbeat to keep relay session active
                try:
                    await self.client._send_alive(
                        self.client._end_id, self.client._group_id, self.client._end_secret
                    )
                    await self.client._send_heartbeat()
                    fail_count = 0
                    _LOGGER.debug("Keepalive OK (alive + heartbeat)")
                except asyncio.TimeoutError:
                    fail_count += 1
                    _LOGGER.warning("Keepalive timeout #%d", fail_count)
                except Exception as err:
                    fail_count += 1
                    _LOGGER.warning("Keepalive error #%d: %s", fail_count, err)
                if fail_count >= 2:
                    _LOGGER.error("Keepalive failed %d times, marking disconnected", fail_count)
                    self.client._e2e_connected = False
                    return
        except asyncio.CancelledError:
            pass

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            # Reconnect E2E if disconnected
            if not self.client._e2e_connected:
                _LOGGER.info("E2E reconnecting...")
                # Cancel old heartbeat
                if self._heartbeat_task:
                    self._heartbeat_task.cancel()
                    self._heartbeat_task = None
                # Close old transport
                await self.client.close()
                # Fresh login + E2E connect
                try:
                    await self.client.login()
                    homes = await self.client.get_homes()
                    if homes:
                        await self.client.get_devices(homes[0]["home_id"])
                except EmaldoAuthError:
                    pass
                device = None
                for dev in self.client.devices:
                    if dev["id"] == self.device_id:
                        device = dev
                        break
                if not device:
                    device = {"id": self.device_id, "model": self.device_model,
                              "end_id": self.client._device_end_id}
                await self.client.e2e_connect(self.home_id, device)
                await self.start_heartbeat()
                _LOGGER.info("E2E reconnected")

            data = await self.client.get_current_data(
                self.home_id, self.device_id, self.device_model
            )
            if not data:
                raise UpdateFailed("Empty response from E2E")
            return data
        except EmaldoAuthError as err:
            self.client._e2e_connected = False
            raise UpdateFailed(f"Auth failed: {err}") from err
        except UpdateFailed:
            raise
        except Exception as err:
            self.client._e2e_connected = False
            raise UpdateFailed(f"E2E error: {err}") from err

    async def async_shutdown(self) -> None:
        """Clean up on shutdown."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        await self.client.close()

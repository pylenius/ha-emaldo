"""Emaldo Cloud API client."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import aiohttp
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
import snappy

from .const import ALL_PROVIDERS, APP_ID, APP_SECRET, API_DOMAIN, STATS_DOMAIN

_LOGGER = logging.getLogger(__name__)


def _rc4(key: str, data: bytes) -> bytes:
    cipher = Cipher(algorithms.ARC4(key.encode()), mode=None)
    encryptor = cipher.encryptor()
    return encryptor.update(data) + encryptor.finalize()


class EmaldoAuthError(Exception):
    """Authentication failed."""


class EmaldoConnectionError(Exception):
    """Connection failed."""


class EmaldoAPIClient:
    """Async client for the Emaldo cloud API."""

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str) -> None:
        self._session = session
        self._email = email
        self._password = password
        self.token: str | None = None
        self.homes: list[dict] = []
        self.devices: list[dict] = []

    async def _call(
        self, domain: str, endpoint: str, data: dict | None = None
    ) -> dict[str, Any]:
        if data is None:
            data = {}
        gmt = int(time.time() * 1000) * 1000000
        data["gmtime"] = gmt
        enc_json = _rc4(APP_SECRET, json.dumps(data).encode()).hex()

        form = {"json": enc_json, "gm": "1"}
        if self.token:
            token_str = f"{self.token}_{gmt}"
            form["token"] = _rc4(APP_SECRET, token_str.encode()).hex()

        url = f"https://{domain}{endpoint}{APP_ID}"
        headers = {"Host": domain, "X-Online-Host": domain}

        try:
            async with self._session.post(
                url, data=form, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                try:
                    body = await resp.json(content_type=None)
                except Exception:
                    text = await resp.text()
                    raise EmaldoConnectionError(f"HTTP {resp.status}: {text[:200]}")
        except aiohttp.ClientError as err:
            raise EmaldoConnectionError(f"Connection error: {err}") from err

        status = body.get("Status")
        if status == -12:
            raise EmaldoAuthError("Token expired")
        if status == 1 and body.get("Result"):
            dec = _rc4(APP_SECRET, bytes.fromhex(body["Result"]))
            try:
                return json.loads(snappy.uncompress(dec))
            except Exception:
                return json.loads(dec)
        return body

    async def login(self) -> bool:
        """Authenticate with the Emaldo API."""
        result = await self._call(
            API_DOMAIN,
            "/user/login/",
            {"email": self._email, "password": self._password},
        )
        if "token" in result:
            self.token = result["token"]
            _LOGGER.debug("Logged in as %s", result.get("uid"))
            return True
        raise EmaldoAuthError(f"Login failed: {result.get('ErrorMessage', 'Unknown error')}")

    async def get_homes(self) -> list[dict]:
        """Get list of homes."""
        result = await self._call(API_DOMAIN, "/home/list-homes/")
        self.homes = result.get("list_homes", [])
        return self.homes

    async def get_devices(self, home_id: str) -> list[dict]:
        """Get list of BMT devices for a home."""
        result = await self._call(
            API_DOMAIN,
            "/bmt/list-bmt/",
            {
                "home_id": home_id,
                "models": ALL_PROVIDERS,
                "page_size": 20,
                "addtime": 0,
                "order": "desc",
            },
        )
        self.devices = result.get("bmts", [])
        return self.devices

    async def get_stats(
        self, home_id: str, device_id: str, model: str, stat_type: str, period: str = "day"
    ) -> dict[str, Any]:
        """Get statistics for a device."""
        return await self._call(
            STATS_DOMAIN,
            f"/bmt/stats/{stat_type}/{period}/",
            {"home_id": home_id, "id": device_id, "model": model},
        )

    async def get_feature(self, home_id: str, device_id: str) -> dict[str, Any]:
        """Get feature flags for a device."""
        return await self._call(
            API_DOMAIN,
            "/bmt/get-feature/",
            {"home_id": home_id, "id": device_id},
        )

    async def get_current_data(
        self, home_id: str, device_id: str, model: str
    ) -> dict[str, Any]:
        """Get current power data from all stat endpoints."""
        data: dict[str, Any] = {}

        for stat_type in ("battery", "grid", "mppt", "load/usage"):
            try:
                result = await self.get_stats(home_id, device_id, model, stat_type)
                if "data" not in result:
                    continue
                entries = result["data"]
                start_time = result.get("start_time", 0)
                # Find last entry with non-zero values
                last = None
                for entry in reversed(entries):
                    if any(v != 0 for v in entry[1:]):
                        last = entry
                        break
                if last:
                    data[stat_type] = {
                        "timestamp": start_time + last[0] * 60,
                        "values": last[1:],
                    }
            except Exception as err:
                _LOGGER.debug("Failed to get %s stats: %s", stat_type, err)

        return data

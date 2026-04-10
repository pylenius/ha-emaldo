"""Emaldo Cloud API + E2E real-time client."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import string
import struct
import time
from typing import Any

import aiohttp
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as crypto_padding
import snappy

from .const import ALL_PROVIDERS, APP_ID, APP_SECRET, API_DOMAIN

_LOGGER = logging.getLogger(__name__)

# E2E method codes (wire format, byte-swapped from APK)
METHOD_CURRENTFLOW = 0x30A0
METHOD_BATTERY_INFO = 0x0510  # get_battery_info — contains SoC at byte[14:16]

# MSCT option types
_OPT_END_ID = 160
_OPT_GROUP_ID = 161
_OPT_RECEIVER_ID = 162
_OPT_AES = 163
_OPT_PAYLOAD_CT = 183
_OPT_STATUS = 192
_OPT_PROXY = 241
_OPT_METHOD = 245
_OPT_MSGID = 246
_OPT_APP_ID = 181


def _rc4(key: str, data: bytes) -> bytes:
    cipher = Cipher(algorithms.ARC4(key.encode()), mode=None)
    encryptor = cipher.encryptor()
    return encryptor.update(data) + encryptor.finalize()


def _aes_enc(iv: str, key: str, data: bytes) -> bytes:
    pd = crypto_padding.PKCS7(128).padder()
    padded = pd.update(data) + pd.finalize()
    c = Cipher(algorithms.AES(key.encode()[:32]), modes.CBC(iv.encode()[:16]))
    e = c.encryptor()
    return e.update(padded) + e.finalize()


def _aes_dec(iv: str, key: str, data: bytes) -> bytes:
    c = Cipher(algorithms.AES(key.encode()[:32]), modes.CBC(iv.encode()[:16]))
    d = c.decryptor()
    padded = d.update(data) + d.finalize()
    u = crypto_padding.PKCS7(128).unpadder()
    return u.update(padded) + u.finalize()


def _rs(n: int = 16) -> str:
    return "".join(random.choice(string.ascii_letters + string.digits) for _ in range(n))


def _mid() -> str:
    return f"and_{_rs(12)}{int(time.time()*1000)}"[:27]


def _build_msct(options: list[tuple[int, bytes]], payload: bytes) -> bytes:
    buf = bytearray([0xD9])
    for i, (ot, ov) in enumerate(options):
        lb = len(ov) & 0x7F
        if i < len(options) - 1:
            lb |= 0x80
        buf.append(lb)
        buf.append(ot)
        buf.extend(ov)
    buf.extend(payload)
    return bytes(buf)


def _parse_response(data: bytes) -> dict[str, Any] | None:
    if len(data) < 2:
        return None
    pos = 1
    options: dict[int, bytes] = {}
    if data[0] & 1:
        while pos < len(data):
            lb = data[pos]
            vl = lb & 0x7F
            hm = bool(lb & 0x80)
            if pos + 1 >= len(data):
                break
            ot = data[pos + 1]
            val = data[pos + 2:pos + 2 + vl] if pos + 2 + vl <= len(data) else b""
            options[ot] = val
            pos += 2 + vl
            if not hm:
                break
    payload = data[pos:] if pos < len(data) else b""
    return {
        "payload": payload,
        "status": int.from_bytes(options.get(_OPT_STATUS, b"\xff\xff"), "big"),
        "aes_key": options.get(_OPT_AES, b"").decode("utf-8", errors="replace"),
        "msg_id": options.get(_OPT_MSGID, b"").decode("utf-8", errors="replace"),
    }


class EmaldoAuthError(Exception):
    """Authentication failed."""


class EmaldoConnectionError(Exception):
    """Connection failed."""


class EmaldoAPIClient:
    """Async client for Emaldo — uses E2E for real-time data, REST for login."""

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str) -> None:
        self._session = session
        self._email = email
        self._password = password
        self.token: str | None = None
        self.homes: list[dict] = []
        self.devices: list[dict] = []
        # E2E state
        self._home_end_id: str = ""
        self._home_end_secret: str = ""
        self._home_group_id: str = ""
        self._end_id: str = ""
        self._end_secret: str = ""
        self._chat_secret: str = ""
        self._group_id: str = ""
        self._device_end_id: str = ""
        self._e2e_host: str = ""
        self._e2e_port: int = 1050
        self._transport: asyncio.DatagramTransport | None = None
        self._responses: dict[str, asyncio.Future] = {}
        self._e2e_connected: bool = False

    async def _rest_call(self, endpoint: str, data: dict | None = None) -> dict[str, Any]:
        if data is None:
            data = {}
        gmt = int(time.time() * 1000) * 1000000
        data["gmtime"] = gmt
        enc_json = _rc4(APP_SECRET, json.dumps(data).encode()).hex()
        form = {"json": enc_json, "gm": "1"}
        if self.token:
            form["token"] = _rc4(APP_SECRET, f"{self.token}_{gmt}".encode()).hex()
        url = f"https://{API_DOMAIN}{endpoint}{APP_ID}"
        try:
            async with self._session.post(url, data=form,
                                           headers={"Host": API_DOMAIN},
                                           timeout=aiohttp.ClientTimeout(total=15)) as resp:
                body = await resp.json(content_type=None)
        except Exception as err:
            raise EmaldoConnectionError(f"REST error: {err}") from err

        if body.get("Status") == -12:
            raise EmaldoAuthError("Token expired")
        if body.get("Status") == 1 and body.get("Result"):
            dec = _rc4(APP_SECRET, bytes.fromhex(body["Result"]))
            try:
                return json.loads(snappy.uncompress(dec))
            except Exception:
                return json.loads(dec)
        return body

    async def login(self) -> bool:
        result = await self._rest_call("/user/login/",
                                        {"email": self._email, "password": self._password})
        if "token" not in result:
            raise EmaldoAuthError(f"Login failed: {result}")
        self.token = result["token"]
        return True

    async def get_homes(self) -> list[dict]:
        result = await self._rest_call("/home/list-homes/")
        self.homes = result.get("list_homes", [])
        return self.homes

    async def get_devices(self, home_id: str) -> list[dict]:
        result = await self._rest_call("/bmt/list-bmt/", {
            "home_id": home_id, "models": ALL_PROVIDERS,
            "page_size": 20, "addtime": 0, "order": "desc",
        })
        self.devices = result.get("bmts", [])
        return self.devices

    async def e2e_connect(self, home_id: str, device: dict) -> None:
        """Establish E2E real-time connection."""
        self._device_end_id = device["end_id"]

        # Home E2E login
        home_e2e = await self._rest_call("/home/e2e-login/", {"home_id": home_id})
        self._home_end_id = home_e2e["end_id"]
        self._home_end_secret = home_e2e["end_secret"]
        self._home_group_id = home_e2e["group_id"]

        # BMT E2E login
        bmt_e2e_resp = await self._rest_call("/bmt/e2e-user-login/", {
            "home_id": home_id, "models": [device["model"]],
            "ids": [{"id": device["id"], "model": device["model"]}],
            "page_size": 0, "addtime": 0,
        })
        bmt_e2e = bmt_e2e_resp["e2es"][0]
        self._end_id = bmt_e2e["end_id"]
        self._end_secret = bmt_e2e["end_secret"]
        self._chat_secret = bmt_e2e["chat_secret"]
        self._group_id = bmt_e2e["group_id"]

        host_str = bmt_e2e.get("host", "e2e2.emaldo.com:1050")
        if ":" in host_str:
            self._e2e_host, ps = host_str.rsplit(":", 1)
            self._e2e_port = int(ps)
        else:
            self._e2e_host = host_str

        # UDP connection
        loop = asyncio.get_event_loop()
        parent = self

        class E2EProtocol(asyncio.DatagramProtocol):
            def connection_made(self, transport):
                pass
            def datagram_received(self, data, addr):
                parent._on_e2e_recv(data)

        self._transport, _ = await loop.create_datagram_endpoint(
            E2EProtocol, remote_addr=(self._e2e_host, self._e2e_port)
        )

        # Authenticate: home alive → BMT alive → heartbeat
        await self._send_alive(self._home_end_id, self._home_group_id, self._home_end_secret)
        await self._send_alive(self._end_id, self._group_id, self._end_secret)
        await self._send_heartbeat()
        self._e2e_connected = True
        _LOGGER.debug("E2E connected to %s:%d", self._e2e_host, self._e2e_port)

    async def _send_heartbeat_safe(self) -> bool:
        """Send heartbeat, return True if successful."""
        try:
            await self._send_heartbeat()
            _LOGGER.debug("Heartbeat OK")
            return True
        except asyncio.TimeoutError:
            _LOGGER.warning("Heartbeat timeout — session may have expired")
            return False
        except Exception as err:
            _LOGGER.warning("Heartbeat error: %s", err)
            return False

    async def _send_alive(self, end_id: str, group_id: str, secret: str) -> None:
        ak = _rs(16)
        msgid = _mid()
        payload = _aes_enc(ak, secret, json.dumps({"__time": int(time.time())}).encode())
        msg = _build_msct([
            (_OPT_END_ID, end_id.encode()), (_OPT_GROUP_ID, group_id.encode()),
            (_OPT_AES, ak.encode()), (_OPT_METHOD, b"alive"),
            (_OPT_MSGID, msgid.encode()), (_OPT_PAYLOAD_CT, b"application/json"),
        ], payload)
        fut = asyncio.get_event_loop().create_future()
        self._responses[msgid] = fut
        self._transport.sendto(msg)
        await asyncio.wait_for(fut, timeout=5)

    async def _send_heartbeat(self) -> None:
        ak = _rs(16)
        msgid = _mid()
        payload = _aes_enc(ak, self._chat_secret, json.dumps({"__time": int(time.time())}).encode())
        msg = _build_msct([
            (_OPT_END_ID, self._end_id.encode()), (_OPT_GROUP_ID, self._group_id.encode()),
            (_OPT_PROXY, struct.pack(">I", 1)), (_OPT_RECEIVER_ID, self._device_end_id.encode()),
            (_OPT_AES, ak.encode()), (_OPT_METHOD, b"heartbeat"),
            (_OPT_APP_ID, APP_ID.encode()), (_OPT_MSGID, msgid.encode()),
            (_OPT_PAYLOAD_CT, b"application/json"),
        ], payload)
        fut = asyncio.get_event_loop().create_future()
        self._responses[msgid] = fut
        self._transport.sendto(msg)
        await asyncio.wait_for(fut, timeout=5)

    async def _send_e2e_command(self, method_code: int, timeout: float = 5.0) -> dict | None:
        ak = _rs(16)
        msgid = _mid()
        payload = _aes_enc(ak, self._chat_secret, b"")
        msg = _build_msct([
            (_OPT_END_ID, self._end_id.encode()), (_OPT_GROUP_ID, self._group_id.encode()),
            (_OPT_PROXY, struct.pack(">I", 1)), (_OPT_RECEIVER_ID, self._device_end_id.encode()),
            (_OPT_AES, ak.encode()), (_OPT_APP_ID, APP_ID.encode()),
            (_OPT_METHOD, struct.pack(">H", method_code)), (_OPT_MSGID, msgid.encode()),
            (_OPT_PAYLOAD_CT, b"application/byte"),
        ], payload)
        fut = asyncio.get_event_loop().create_future()
        self._responses[msgid] = fut
        self._transport.sendto(msg)
        try:
            resp = await asyncio.wait_for(fut, timeout=timeout)
            if resp["payload"] and resp["aes_key"] and resp["status"] == 0:
                try:
                    resp["decrypted"] = _aes_dec(resp["aes_key"], self._chat_secret, resp["payload"])
                except Exception:
                    resp["decrypted"] = None
            return resp
        except asyncio.TimeoutError:
            self._responses.pop(msgid, None)
            return None

    def _on_e2e_recv(self, data: bytes) -> None:
        parsed = _parse_response(data)
        if not parsed:
            return
        msg_id = parsed["msg_id"]
        if msg_id in self._responses:
            fut = self._responses.pop(msg_id)
            if not fut.done():
                fut.set_result(parsed)

    async def get_current_data(self, home_id: str, device_id: str, model: str) -> dict[str, Any]:
        """Get real-time power data via E2E."""
        if not self._e2e_connected:
            _LOGGER.warning("get_current_data called but E2E not connected")
            return {}

        data: dict[str, Any] = {}

        # Currentflow — all power values
        try:
            resp = await self._send_e2e_command(METHOD_CURRENTFLOW)
            if resp and resp.get("decrypted") and len(resp["decrypted"]) >= 12:
                d = resp["decrypted"]
                data["battery_w"] = struct.unpack_from("<h", d, 0)[0] * 100
                data["solar_w"] = struct.unpack_from("<h", d, 2)[0] * 100
                data["grid_w"] = struct.unpack_from("<h", d, 4)[0] * 100
                data["load_w"] = -struct.unpack_from("<h", d, 6)[0] * 100
                data["vehicle_w"] = struct.unpack_from("<h", d, 10)[0] * 100 if len(d) >= 12 else 0
            elif resp and resp.get("status") == 21204:
                _LOGGER.warning("Session expired (21204), marking disconnected for reconnect")
                self._e2e_connected = False
                return {}
            elif resp:
                _LOGGER.warning("Currentflow: status=%s, decrypted=%s", resp.get("status"), bool(resp.get("decrypted")))
            else:
                _LOGGER.warning("Currentflow: no response (timeout)")
        except Exception as err:
            _LOGGER.error("Currentflow error: %s", err)

        # Battery info — SoC at byte[14:16] as u16LE
        try:
            resp2 = await self._send_e2e_command(METHOD_BATTERY_INFO)
            if resp2 and resp2.get("decrypted") and len(resp2["decrypted"]) >= 16:
                data["soc"] = struct.unpack_from("<H", resp2["decrypted"], 14)[0]
            elif resp2:
                _LOGGER.debug("Battery info: status=%s", resp2.get("status"))
            else:
                _LOGGER.debug("Battery info: no response")
        except Exception as err:
            _LOGGER.debug("Battery info error: %s", err)

        _LOGGER.debug("E2E data: %s", {k: v for k, v in data.items() if k != "decrypted"})
        return data

    async def close(self) -> None:
        if self._transport:
            self._transport.close()
            self._transport = None
        self._e2e_connected = False

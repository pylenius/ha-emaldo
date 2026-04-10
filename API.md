# Emaldo API Documentation

Reverse-engineered from the Emaldo Android app v2.8.3 (com.hps.emaldo / Dinsafer platform).

## Overview

Emaldo devices (Power Core, Power Store, Power Sense) communicate via two channels:

- **Cloud API** — REST API for authentication, device management, and statistics
- **BLE** — Local Bluetooth LE for WiFi provisioning and initial setup

## Cloud API

### Base URLs

| Domain | Purpose |
|--------|---------|
| `api.emaldo.com` | Authentication, device management, home management |
| `dp.emaldo.com` | Device statistics (battery, solar, grid, load) |

All domains resolve to the same IP (34.79.224.71) but use virtual hosting.

### App Credentials

Every request uses these app-level credentials (hardcoded in the APK):

```
APP_ID:     CXRqKjx2MzSAkdyucR9NDyPiiQR2vQcQ
APP_SECRET: FpF4Uqiio9k8p9VUSX36UZxy9wLs7ybT
```

### Request Encryption

All API requests use **RC4 encryption** with the APP_SECRET as the key.

#### Request format

All requests are `POST` with `application/x-www-form-urlencoded` body containing:

| Field | Description |
|-------|-------------|
| `json` | RC4-encrypted hex-encoded JSON payload |
| `token` | RC4-encrypted hex-encoded auth token (omit for login) |
| `gm` | Always `"1"` |

#### Encrypting the JSON payload

1. Build a JSON object with the request parameters
2. Add `"gmtime": <nanosecond_timestamp>` (milliseconds * 1,000,000)
3. RC4-encrypt the JSON string with APP_SECRET
4. Hex-encode the ciphertext

```python
import time, json
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

def rc4(key: str, data: bytes) -> bytes:
    c = Cipher(algorithms.ARC4(key.encode()), mode=None)
    return c.encryptor().update(data) + c.encryptor().finalize()

gmtime = int(time.time() * 1000) * 1000000
payload = {"email": "user@example.com", "password": "secret", "gmtime": gmtime}
encrypted = rc4(APP_SECRET, json.dumps(payload).encode()).hex()
```

#### Encrypting the auth token

1. Concatenate: `<token>_<gmtime>`
2. RC4-encrypt with APP_SECRET
3. Hex-encode

```python
token_str = f"{token}_{gmtime}"
encrypted_token = rc4(APP_SECRET, token_str.encode()).hex()
```

#### URL format

All URLs append the APP_ID:

```
https://{domain}{endpoint}{APP_ID}
```

Example: `https://api.emaldo.com/user/login/CXRqKjx2MzSAkdyucR9NDyPiiQR2vQcQ`

### Response Decryption

Responses are JSON with this structure:

```json
{
  "Status": 1,
  "Action": "",
  "Cmd": "",
  "ErrorMessage": "",
  "MessageId": "",
  "Result": "<hex-encoded encrypted data>"
}
```

**Status codes:**
| Status | Meaning |
|--------|---------|
| `1` | Success |
| `0` | Error (see ErrorMessage) |
| `-11` | User not found |
| `-12` | Token expired (re-authenticate) |
| `-54` | Invalid parameters or endpoint |

To decrypt `Result`:
1. Hex-decode the string
2. RC4-decrypt with APP_SECRET
3. Snappy-decompress (some responses skip this step)
4. Parse as JSON

```python
import snappy

decrypted = rc4(APP_SECRET, bytes.fromhex(result_hex))
try:
    data = json.loads(snappy.uncompress(decrypted))
except:
    data = json.loads(decrypted)
```

---

## Authentication

### Login

```
POST /user/login/{APP_ID}
Host: api.emaldo.com
```

**Request payload:**
```json
{
  "email": "user@example.com",
  "password": "password123",
  "gmtime": 1775810447277986903
}
```

**Decrypted response:**
```json
{
  "avatar": "app_user_avatar/...",
  "avatar_url": "https://files.emaldo.com/...",
  "email": "user@example.com",
  "gmtime": 1775810447277986903,
  "phone": "",
  "reg_time": 1770302941085403330,
  "token": "uid_fa107d6b846e97bb159483d1f6ecfe5d",
  "uid": "username",
  "user_id": "6984adddd14f37106f01c5b4"
}
```

The `token` is used for all subsequent requests.

### Logout

```
POST /user/logout/{APP_ID}
Host: api.emaldo.com
```

---

## Home Management

### List Homes

```
POST /home/list-homes/{APP_ID}
Host: api.emaldo.com
```

**Request payload:** `{}` (empty, just gmtime)

**Response:**
```json
{
  "gmtime": 1775810512745143057,
  "list_homes": [
    {
      "home_id": "6984adddd14f37106f01c5b5",
      "home_name": "HOME",
      "level": 30
    }
  ]
}
```

### E2E Login (WebSocket/real-time)

```
POST /home/e2e-login/{APP_ID}
Host: api.emaldo.com
```

**Request:** `{"home_id": "<home_id>"}`

**Response:**
```json
{
  "chat_secret": "28TCeungHhmGkiChDc9X4HAvusXKVOKN",
  "end_id": "bGPyCpKsyjHR4pHljXbEgJMIkr4Mpv85",
  "end_secret": "H95DdfVInwD7rMxmnVHT4xYO42QqATQR",
  "group_id": "WeujWKtzkNWCW77LO5FESUVZbHjI5m@0",
  "host": "e2e2.emaldo.com:1050",
  "util_host": "e2e2.emaldo.com:1051"
}
```

### Other Home Endpoints

```
POST /home/get-info/{APP_ID}
POST /home/new-home/{APP_ID}
POST /home/rename-home/{APP_ID}
POST /home/delete-home/{APP_ID}
POST /home/list-members/{APP_ID}
POST /home/new-invitation-code/{APP_ID}
POST /home/check-invitation-code/{APP_ID}
```

---

## Device Management (BMT)

### List Devices

```
POST /bmt/list-bmt/{APP_ID}
Host: api.emaldo.com
```

**Request:**
```json
{
  "home_id": "<home_id>",
  "models": ["HP5000", "HP5001", "PC1-BAK15-HS10", "PS1-BAK10-HS10", "VB1-BAK5-HS10", "PC3", "PSE1", "PSE2"],
  "page_size": 20,
  "addtime": 0,
  "order": "desc"
}
```

**Response:**
```json
{
  "bmts": [
    {
      "name": "Power Core 2.0",
      "id": "euPufCjZ3IaOwNfe",
      "group_id": "MJjln1Ec2tUkBvWRkqXjKCf58OnyEv@0",
      "end_id": "b7nXwJ9ZndM9zQtFvxUs1uIA3ZZHK9FW",
      "addr": "91.157.160.53:56562",
      "model": "PC1-BAK15-HS10",
      "addtime": 1770303038007902198,
      "country_code": "FI",
      "delivery_area": "FI",
      "third_devices": []
    }
  ],
  "count": 1
}
```

### Device Feature Flags

```
POST /bmt/get-feature/{APP_ID}
Host: api.emaldo.com
```

**Request:** `{"home_id": "<home_id>", "id": "<device_id>"}`

**Response:**
```json
{
  "elec_support": true,
  "grid_conn_support": false,
  "grid_to_battery": true
}
```

### Other Device Endpoints

```
POST /bmt/search-bmt/{APP_ID}           — Search devices by ID
POST /bmt/bind-inverter/{APP_ID}         — Bind inverter
POST /bmt/delete/{APP_ID}               — Delete device
POST /bmt/rename/{APP_ID}               — Rename device
POST /bmt/get-region/{APP_ID}           — Get region settings
POST /bmt/update-region/{APP_ID}        — Update region
POST /bmt/save-location/{APP_ID}        — Save GPS location
POST /bmt/get-elec-price-info/{APP_ID}  — Electricity pricing
POST /bmt/get-locally-switch/{APP_ID}   — Local control toggle
POST /bmt/set-locally-switch/{APP_ID}   — Set local control
```

---

## Statistics (Real-time Power Data)

All statistics endpoints use `dp.emaldo.com` and include a time period in the URL path.

### URL pattern

```
POST /bmt/stats/{stat_type}/{period}/{APP_ID}
Host: dp.emaldo.com
```

**Periods:** `day`, `week`, `month`, `year`

**Request:**
```json
{
  "home_id": "<home_id>",
  "id": "<device_id>",
  "model": "<model>"
}
```

### Response format

All stats responses share this structure:

```json
{
  "start_time": 1775768400,
  "timezone": "Europe/Helsinki",
  "interval": 5,
  "data": [
    [0, 160, 0, 0],
    [5, 180, 0, 0],
    ...
  ]
}
```

- `start_time` — Unix timestamp of the start of the period
- `interval` — Minutes between data points
- `data` — Array of `[minute_offset, value1, value2, ...]`
- Values are in **watts** (divide by 1000 for kW)

### Battery Stats

```
POST /bmt/stats/battery/day/{APP_ID}
```

Data format: `[minute_offset, charge_w, discharge_w, grid_charge_w]`

| Index | Field | Unit | Description |
|-------|-------|------|-------------|
| 0 | minute_offset | min | Minutes since start_time |
| 1 | charge | W | Battery charging power |
| 2 | discharge | W | Battery discharging power |
| 3 | grid_charge | W | Grid-to-battery charging power |

### Solar (MPPT) Stats

```
POST /bmt/stats/mppt/day/{APP_ID}
```

Data format: `[minute_offset, string1_w, string2_w, string3_w]`

| Index | Field | Unit | Description |
|-------|-------|------|-------------|
| 0 | minute_offset | min | Minutes since start_time |
| 1 | string_1 | W | MPPT string 1 power |
| 2 | string_2 | W | MPPT string 2 power |
| 3 | string_3 | W | MPPT string 3 power (if present) |

### Grid Stats

```
POST /bmt/stats/grid/day/{APP_ID}
```

Data format: `[minute_offset, v1, v2, v3, v4, v5, v6, v7, v8, v9, v10, v11, v12]`

Grid data contains 12 values — likely per-phase (L1/L2/L3) import/export data. Observed so far:

| Index | Likely meaning |
|-------|---------------|
| 3 | Grid export power (W) |
| 5 | Grid import power (W) |

*(Other indices need further investigation with multi-phase setups)*

### Load Usage Stats

```
POST /bmt/stats/load/usage/day/{APP_ID}
```

Data format: `[minute_offset, grid_load_w, backup_load_w, other_w]`

| Index | Field | Unit | Description |
|-------|-------|------|-------------|
| 0 | minute_offset | min | Minutes since start_time |
| 1 | grid_load | W | Load powered from grid |
| 2 | backup_load | W | Load powered from battery/solar |
| 3 | other | W | Other load |

### Other Stats Endpoints

```
POST /bmt/stats/battery-v2/day/{APP_ID}
POST /bmt/stats/mppt-v2/day/{APP_ID}
POST /bmt/stats/eco/day/{APP_ID}
POST /bmt/stats/eco-v2/day/{APP_ID}
POST /bmt/stats/revenue/day/{APP_ID}
POST /bmt/stats/revenue-v2/day/{APP_ID}
POST /bmt/stats/b-sensor/{APP_ID}
POST /bmt/stats/battery/power-level/day/{APP_ID}
POST /bmt/stats/get-charging-discharging-plans/{APP_ID}
POST /bmt/stats/get-charging-discharging-plans-v2-minute/{APP_ID}
POST /bmt/stats/get-charging-discharging-plans-v3/{APP_ID}
```

---

## BLE Protocol

Used for initial WiFi provisioning and local configuration.

### Device Types and UUIDs

| Device | Service UUID | Write UUID | Notify UUID |
|--------|-------------|------------|-------------|
| Power Core 2.0 | `bcf25cee-fbad-4f85-a41c-8da2bd9ed1ac` | `156df971-1dd5-44d6-a381-f271821f6804` | `1c7d885f-e617-49e9-8e5d-6ac6d9ed8765` |
| BMT (Battery) | `23593c00-69b8-4e6d-aaca-7151114385e2` | `23593c01-...` | `23593c02-...` |
| EG (Energy Gateway) | `23593c00-69b8-431b-a241-b9afa31c160b` | `23593c01-...` | `23593c02-...` |
| Security Panel | `23593c00-69b8-419b-84f3-a3fe7a354cdb` | `23593c01-...` | `23593c02-...` |

### BLE Encryption

BLE communication uses **AES-256-CBC with PKCS5 padding**:

```
IV:  dfcf28d0734569a6        (16 bytes)
Key: fbade9e36a3f36d3d676c1b808451dd7  (32 bytes)
```

### BLE Commands (JSON, AES-encrypted)

#### Provisioning Commands

| Command | Description |
|---------|-------------|
| `{"cmd": "get_version"}` | Get firmware version |
| `{"cmd": "get_model"}` | Get device model |
| `{"cmd": "get_valid_models"}` | List supported models |
| `{"cmd": "get_wifi_list"}` | Scan WiFi networks (streams multiple responses) |
| `{"cmd": "get_ethernet_state"}` | Check ethernet connection |
| `{"cmd": "set_wifi_name", "data": "<ssid>"}` | Set WiFi SSID |
| `{"cmd": "set_wifi_password", "data": "<pass>"}` | Set WiFi password |
| `{"cmd": "set_network"}` | Connect to WiFi |
| `{"cmd": "set_app_id", "data": "<app_id>"}` | Set app ID |
| `{"cmd": "set_app_secret", "data": "<secret>"}` | Set app secret |
| `{"cmd": "set_http_host", "data": "<domain>"}` | Set API server |
| `{"cmd": "set_data_host", "data": "<domain>"}` | Set data server |
| `{"cmd": "set_home", "data": "<home_id>"}` | Set home ID |
| `{"cmd": "set_model", "data": "<model>"}` | Set device model |
| `{"cmd": "register", "source": 0}` | Register device |
| `{"cmd": "set_tz", "tz": "tzn+03:00:00"}` | Set timezone |
| `{"cmd": "update_config"}` | Apply configuration |

#### BLE Response Format

```json
{"cmd": "get_version", "result": "v2.24.7", "status": 1}
{"cmd": "get_model", "result": "PC1-BAK15-HS10", "status": 1}
{"cmd": "get_wifi_list", "result": "MyNetwork", "rssi": -45, "auth": true, "status": 2}
{"cmd": "get_wifi_list", "result": "", "rssi": 0, "auth": false, "status": 1}
```

- `status: 1` — success / end of stream
- `status: 2` — streaming (more data coming)
- `status: 0` — error / not supported

### WiFi Provisioning Flow

1. BLE connect to device
2. `get_version` → check firmware
3. `get_wifi_list` → scan networks
4. `set_wifi_name` → set SSID
5. `set_wifi_password` → set password
6. `set_network` → connect to WiFi
7. `set_app_id` → configure app ID
8. `set_app_secret` → configure app secret
9. `set_http_host` → set API domain
10. `set_data_host` → set stats domain
11. `set_home` → assign to home
12. `set_model` → set device model
13. `register` → register with cloud
14. `set_tz` → set timezone
15. `update_config` → apply all settings

---

## Device Models

| Model ID | Product Name | BLE Service |
|----------|-------------|-------------|
| HP5000 | Legacy | `70D1EA0C-...` |
| HP5001 | Legacy | `23593c00-...-a3fe7a354cdb` |
| PC1-BAK15-HS10 | Power Core 2.0 | `bcf25cee-...` |
| PS1-BAK10-HS10 | Power Store | `70D1EA0C-...` + `6e0655ab-...` |
| VB1-BAK5-HS10 | Power Pulse | `6e0655ab-...` |
| PC3 | Power Core 3.0 | `d977e25f-...` |
| PSE1 | Power Sense 1 | `fbec41de-...` |
| PSE2 | Power Sense 2 | `12de0286-...` |

## Real-time Communication Channels

The Emaldo platform uses three different real-time channels depending on device type:

### WebSocket (Security Panel only)

```
wss://api.emaldo.com/device/ws/v2/CXRqKjx2MzSAkdyucR9NDyPiiQR2vQcQ
```

Used exclusively by the **security panel** system (alarm, sensors, sirens). Not used by BMT/battery devices.

**Authentication:**

On WebSocket open, the app sends an RC4-encrypted auth message:

```
RC4_HEX_UPPER( user_token + "&" + panel_device_token + "_" + timestamp_micros )
```

- `user_token` — from `/user/login/` response
- `panel_device_token` — from the security panel device (not available on BMT-only systems)
- `timestamp_micros` — `System.currentTimeMillis() * 1000`

**Messages:**

| Message | Meaning |
|---------|---------|
| `"1"` | Authentication successful |
| `"-1"` | Authentication failed / forced logout |
| `"-2"` | Device offline |
| JSON object | Device event or command response |

**JSON message structure:**
```json
{
  "Action": "/device/result",
  "Cmd": "command_name",
  "Status": 1,
  "MessageId": "...",
  "Result": "<RC4+Snappy encrypted payload>"
}
```

Known Actions:
- `/device/result` — Command response
- `/device/revice` — Device event (alarm, sensor trigger)
- `/device/ping` — Device heartbeat (battery level, signal, IP)
- `/device/sim` — SIM card status
- `/device/offline` — Device went offline
- `/device/cmdack` — Command acknowledgment

**Note:** BMT-only installations (no security panel) cannot authenticate to the WebSocket — the auth requires a panel device token that doesn't exist.

### E2E / MSCT Protocol (BMT devices)

BMT devices use a custom **E2E (end-to-end) protocol** with **MSCT binary framing over raw UDP** for real-time command/control. **Corrected from earlier analysis:** the protocol does NOT use KCP — it's plain MSCT messages sent as UDP datagrams directly. This was confirmed via packet capture from the real Android app.

#### Step 1: E2E Login (two endpoints)

**Home-level E2E login:**
```
POST /home/e2e-login/{APP_ID}
Host: api.emaldo.com
```

**Request:** `{"home_id": "<home_id>"}`

**Response:**
```json
{
  "chat_secret": "28TCeungHhmGkiChDc9X4HAvusXKVOKN",
  "end_id": "bGPyCpKsyjHR4pHljXbEgJMIkr4Mpv85",
  "end_secret": "H95DdfVInwD7rMxmnVHT4xYO42QqATQR",
  "group_id": "WeujWKtzkNWCW77LO5FESUVZbHjI5m@0",
  "host": "e2e2.emaldo.com:1050",
  "util_host": "e2e2.emaldo.com:1051"
}
```

**BMT-specific E2E login (preferred for battery devices):**
```
POST /bmt/e2e-user-login/{APP_ID}
Host: api.emaldo.com
```

**Request:**
```json
{
  "home_id": "<home_id>",
  "models": ["PC1-BAK15-HS10"],
  "ids": [{"id": "<device_id>", "model": "<model>"}],
  "page_size": 0,
  "addtime": 0
}
```

**Response:**
```json
{
  "e2es": [
    {
      "id": "euPufCjZ3IaOwNfe",
      "group_id": "MJjln1Ec2tUkBvWRkqXjKCf58OnyEv@0",
      "end_id": "bPPlcsrmDbiEfXDyW1UEW2Zbdsb3o1j1",
      "end_secret": "6UcSsEdggnWGLvnG91tC6QY21Y1pWw7J",
      "chat_secret": "wv7HIZrDaV9rjCtHM2NB9lpMRWXNkM8U",
      "host": "e2e2.emaldo.com:1050",
      "util_host": "e2e2.emaldo.com:1051",
      "addtime": 1770303038007902198
    }
  ],
  "count": 1
}
```

The BMT endpoint returns per-device credentials. Each session generates fresh `end_id`, `end_secret`, and `chat_secret` values.

#### Step 2: KCP Connection

The app connects via UDP to `e2e2.emaldo.com:1050` (35.187.68.18) using the KCP protocol.

**Protocol stack (confirmed via packet capture):**
```
Application: Binary command codes + AES-encrypted payloads
    ↓
Framing: MSCT binary messages (header + TLV options + payload)
    ↓
Transport: Raw UDP datagrams (NO KCP framing)
    ↓
Network: UDP to e2e2.emaldo.com:1050 (35.187.68.18)
```

**Key correction:** Despite the APK containing KCP code, the actual BMT proxy communication uses **raw MSCT over UDP** — each MSCT message is a single UDP datagram. KCP is only used for P2P/LAN direct connections, not the proxy relay.

#### Step 3: MSCT Message Layer

On top of KCP, the app uses a custom binary protocol called MSCT (Message Secure Communication Transport).

**MSCT message format:**

```
[Header byte]
[Option TLV 1] [Option TLV 2] ... [Option TLV N]
[Encrypted payload]
```

**Header byte:**
```
Bits 7-4: msgType (CON=13, ACK=14, NOCON=12, QOS=15)
Bits 3-1: channelType (NORCHAN1=4, ASYNCCHAN1=0, etc.)
Bit 0:    hasOptions (1 if TLV options follow)
```

Example: CON on NORCHAN1 with options → `((13 << 4) & 0xF0) | ((4 << 1) & 0x0E) | 1` = `0xD9`

**Option TLV format:**
```
[length_byte] [type_byte] [value_bytes...]
```
- `length_byte`: lower 7 bits = value length in bytes. Bit 7 (0x80) = continuation flag (set if more options follow, clear on last option)
- `type_byte`: option type identifier
- `value_bytes`: UTF-8 encoded strings or raw bytes

**Option types:**

| Type | Name | Value |
|------|------|-------|
| 160 (0xA0) | OPTION_END_ID | Device endpoint ID (string) |
| 161 (0xA1) | OPTION_GROUP_ID | Group ID (string) |
| 162 (0xA2) | OPTION_RECEIVER_ID | Target device ID (string) |
| 163 (0xA3) | OPTION_AES | Random 16-char AES session key (string) |
| 164 (0xA4) | OPTION_SEQ | Sequence number |
| 177 (0xB1) | OPTION_SERVICE | Service identifier |
| 178 (0xB2) | OPTION_METHOD_1 | Alternative method |
| 179 (0xB3) | OPTION_DOMAIN | Domain |
| 181 (0xB5) | OPTION_APP_ID | Application ID (string) |
| 183 (0xB7) | OPTION_PAYLOAD_CONTENT_TYPE | "application/json" or "application/byte" |
| 192 (0xC0) | OPTION_STATUS | Response status code |
| 193 (0xC1) | OPTION_MESSAGE | Error message |
| 240 (0xF0) | OPTION_MULTIPARTDATA | Multipart data flag |
| 241 (0xF1) | OPTION_PROXY | Proxy flag (byte: 1=via proxy) |
| 242 (0xF2) | OPTION_P2P | P2P connection flag |
| 243 (0xF3) | OPTION_TOKEN | Auth token |
| 244 (0xF4) | OPTION_URL | URL |
| 245 (0xF5) | OPTION_METHOD | Method name (string) |
| 246 (0xF6) | OPTION_MSGID | Unique message ID (string) |
| 247 (0xF7) | OPTION_SESSID | Session ID |
| 248 (0xF8) | OPTION_QOSLEVEL | QoS level |

#### Step 4: AES Encryption — Two Keys for Two Purposes

All payloads use AES-256-CBC with PKCS5 padding. The `Encryption.encryptAes(iv, key, data)` convention: **first param = IV, second = key**.

The critical discovery (confirmed via implementation + packet capture): **different secrets are used for different message types:**

| Message type | IV (16 bytes) | Key (32 bytes) | Purpose |
|-------------|---------------|----------------|---------|
| **alive** | random `OPTION_AES` | `end_secret` | Relay server authentication |
| **heartbeat** | random `OPTION_AES` | `chat_secret` | Device channel registration |
| **commands** | random `OPTION_AES` | `chat_secret` | Device data queries |
| **responses** | response `OPTION_AES` | `chat_secret` | Decrypt response payloads |

- **`end_secret`** (from e2e-login) — authenticates with the relay server only. Used for alive messages.
- **`chat_secret`** (from e2e-login) — communicates with the device via the relay. Used for heartbeat and all commands/responses.

Each message generates a random 16-char `OPTION_AES` key used as the IV. Responses include their own `OPTION_AES` for decrypting the response payload.

#### Step 5: Connection Handshake (confirmed working)

The connection requires three steps before commands work:

```
1. → alive (home e2e credentials, end_secret encryption)
   ← alive ACK status=0

2. → alive (BMT e2e credentials, end_secret encryption)  
   ← alive ACK status=0

3. → heartbeat (BMT credentials, chat_secret encryption, with PROXY + RECEIVER)
   ← heartbeat ACK status=0

4. → commands (BMT credentials, chat_secret encryption)
   ← command responses with binary data
```

**alive message** (authentication with relay):
```
Header:  0xD9 (CON, NORCHAN1, hasOptions)
Options:
  [160] END_ID:       32 bytes (from e2e-login)
  [161] GROUP_ID:     32 bytes (from e2e-login)
  [163] AES:          16 bytes (random key)
  [245] METHOD:       5 bytes  ("alive")
  [246] MSGID:        27 bytes ("and_..." + timestamp)
  [183] CONTENT_TYPE: 16 bytes ("application/json")
Payload: 32 bytes (AES_encrypt(aes_key, end_secret, {"__time": <unix_ts>}))
```

**heartbeat message** (register device proxy channel):
```
Header:  0xD9
Options:
  [160] END_ID:       32 bytes (BMT e2e end_id)
  [161] GROUP_ID:     32 bytes (device group_id)
  [241] PROXY:        4 bytes  (int32 = 1)
  [162] RECEIVER_ID:  32 bytes (device end_id from BMT list — permanent)
  [163] AES:          16 bytes (random key)
  [245] METHOD:       9 bytes  ("heartbeat")
  [181] APP_ID:       32 bytes ("CXRqKjx2MzSAkdyucR9NDyPiiQR2vQcQ")
  [246] MSGID:        27 bytes
  [183] CONTENT_TYPE: 16 bytes ("application/json")
Payload: 32 bytes (AES_encrypt(aes_key, chat_secret, {"__time": <unix_ts>}))
```

**command message** (query device):
```
Header:  0xD9
Options:
  [160] END_ID:       32 bytes (BMT e2e end_id)
  [161] GROUP_ID:     32 bytes (device group_id)
  [241] PROXY:        4 bytes  (int32 = 1)
  [162] RECEIVER_ID:  32 bytes (device end_id from BMT list)
  [163] AES:          16 bytes (random key)
  [181] APP_ID:       32 bytes
  [245] METHOD:       2 bytes  (binary command code, big-endian)
  [246] MSGID:        27 bytes
  [183] CONTENT_TYPE: 16 bytes ("application/byte")
Payload: 16 bytes (AES_encrypt(aes_key, chat_secret, b""))  ← empty, PKCS7-padded
```

**response message:**
```
Header:  0xE3 (ACK, ASYNCCHAN1)
Options include: STATUS (2B, 0=success), MSGID (matches request), METHOD (echoes request),
                 AES (response key for decryption), END_ID, RECEIVER_ID, GROUP_ID
Payload: AES_encrypt(response_aes_key, chat_secret, binary_data)
```

The app fires ~16 commands simultaneously after the heartbeat. Responses arrive asynchronously, matched by MSGID.

#### Binary Method Codes (confirmed)

Wire codes are **byte-swapped** from APK source codes. E.g., APK `0xA030` → wire `0x30A0`.

| Wire code | APK code | Command | Payload | Response |
|-----------|----------|---------|---------|----------|
| `0x30A0` | `0xA030` | **get_global_currentflow** | empty | 22B — all power values |
| `0x17A0` | `0xA017` | get_cabinet_state | empty | 11B — SoC |
| `0x18A0` | `0xA018` | get_battery_allinfo | empty | 57B |
| `0x0410` | `0x1004` | get_inverter_info | index byte | 24B |
| `0x0A10` | `0x100A` | get_inverter_input_info | empty | 9B |
| `0x0110` | `0x1001` | get_inverter_output_info | empty | 3B |
| `0x0810` | `0x1008` | get_mppt_state | empty | 7B+ |
| `0x25A0` | `0xA025` | get_mcu_info | empty | 24B |
| `0x21A0` | `0xA021` | get_global_loadstate | empty | 91B — device info |
| `0x10A0` | `0xA010` | get_global_exceptions | empty | 22B |
| `0x11A0` | `0xA011` | get_ev_state | empty | 57B |
| `0x0710` | `0x1007` | get_mode | empty | 26B |
| `0x04A0` | `0xA004` | get_charge_strategies | empty | 1B |
| `0x32A0` | `0xA032` | get_advance_info | empty | 6B |
| `0x07A0` | `0xA007` | get_communicate_signal | empty | 1B |
| `0x02A0` | `0xA002` | get_emergency_charge | empty | 2B |
| `0x06A0` | `0xA006` | get_virtual_power_plant | empty | 11B |

#### Currentflow Response Format (0x30A0) — THE key command

This single command returns all dashboard power values. Values are **signed 16-bit little-endian in hectowatts** (÷10 for kW).

```
Offset  Type    Field              Sign convention
[0:2]   i16LE   batteryWat         + = discharge, - = charge
[2:4]   i16LE   solarWat           + = producing
[4:6]   i16LE   gridWat            + = import, - = export
[6:8]   i16LE   additionLoadWat    - = consuming (show as positive)
[8:10]  i16LE   otherLoadWat
[10:12] i16LE   vehicleWat
[12:14] u16LE   ip2Wat
[14:16] u16LE   op2Wat
[16]    byte    gridValid          1 = grid CT connected
[17]    byte    bsensorValid       1 = battery sensor valid
[18]    byte    solarEfficiency    efficiency type enum
[19]    byte    thirdpartyPVOn     1 = third-party PV enabled
[20:22] i16LE   dualPowerWat
```

**Verified example** (Grid exporting 3.1kW):
```
Hex: 00003000e1ffefff000000000000000001010300efff
batteryWat=0    → 0.0 kW (idle)
solarWat=48     → 4.8 kW ✓
gridWat=-31     → -3.1 kW (export) ✓
loadWat=-17     → 1.7 kW ✓
vehicleWat=0    → 0.0 kW ✓
```

#### Connection Modes

The app tries three connection modes in priority order:

1. **LAN** — Direct local network (JSON over KCP)
2. **P2P** — NAT traversal (JSON over KCP)
3. **Proxy** — Relay via `e2e2.emaldo.com:1050` (MSCT binary over raw UDP)

The proxy mode is the most common for remote access and is what the capture shows.

#### Implementation Status (WORKING)

**Fully working (confirmed 2026-04-10):**
- Raw MSCT over UDP to `e2e2.emaldo.com:1050`
- Two-phase authentication: alive (end_secret) → heartbeat (chat_secret)
- All 16 BMT command codes return data with status=0
- Response payload decryption with chat_secret produces valid binary data
- Python implementation: `emaldo_e2e.py`

**Verified command responses:**

| Command | Method | Response | Data |
|---------|--------|----------|------|
| currentflow | 0x45A0 | 4B | Power flow summary |
| inverter_info | 0x0210 | 24B | Inverter model, firmware, state |
| inverter_input | 0x02A0 | 9B | Grid input power |
| inverter_output | 0x43A0 | 3B | Grid output |
| battery_allinfo | 0x0410 | status=1 | May need index parameter |
| mppt_state | 0x17A0 | 11B | Solar string power |
| cabinet_allinfo | 0x07A0 | 5B | Battery cabinet info |
| global_loadstate | 0x10A0 | 91B | Network info, device name, IPs |
| global_exceptions | 0x30A0 | 22B | Error/fault codes |
| charge_strategies | 0x11A0 | 1B | Charge mode |
| advance_info | 0x20A0 | 6B | Advanced settings |
| comm_signal | 0x25A0 | 1B | Signal strength |
| mode | 0x33A0 | 26B | Operating mode |
| ev_state | 0x18A0 | 57B | EV charger state |
| emergency_charge | 0x52A0 | 2B | Emergency charge state |
| virtualpowerplant | 0x81A0 | 11B | VPP state |

**Fully decoded:**
- `get_global_currentflow` (0x30A0) — Solar, Grid, Battery, Load, Vehicle power in hectowatts
- Wire method codes are byte-swapped from APK source codes
- Sign convention: positive = producing/discharging/importing, negative = consuming/exporting/charging
- Python implementation: `emaldo_e2e.py` — real-time data in <2 seconds

### MQTT

The Paho MQTT library (`org.eclipse.paho.client.mqttv3`) is bundled in the APK but is **not actively used** by the BMT module. References to `MqttTopic.TOPIC_LEVEL_SEPARATOR` are used only as a string constant (`"/"`). There is no MQTT broker connection for BMT devices.

---

## Other Infrastructure

| Service | URL | Protocol |
|---------|-----|----------|
| API server | `api.emaldo.com` | HTTPS (REST) |
| Stats server | `dp.emaldo.com` | HTTPS (REST) |
| E2E relay | `e2e2.emaldo.com:1050` | KCP (UDP) |
| E2E util | `e2e2.emaldo.com:1051` | KCP (UDP) |
| DNS-over-HTTPS | `doh.emaldo.com` | HTTPS |
| Static content | `s.emaldo.com` | HTTPS |
| Language files | `local.dinsafer.com` | HTTP |
| Push notifications | `dou.emaldo.com` | HTTPS |
| AWS Kinesis Video | `kinesisvideo.us-west-2.amazonaws.com` | HTTPS |
| Cognito pool | `77917499-3a44-4966-9bf3-3798a134ac94` | AWS |

All API domains (`api.emaldo.com`, `dp.emaldo.com`, `dou.emaldo.com`) resolve to the same IP (34.79.224.71) and use virtual hosting.

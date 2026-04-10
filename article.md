# How I Reverse-Engineered My Home Battery's Protocol in One Day — With an AI Pair Programmer

*From a sealed Android APK to real-time Home Assistant sensors, in a single sitting.*

---

I have an Emaldo Power Core 2.0 — a 15 kWh home battery system with solar inverter. It works great. The app works great. But I wanted my data in Home Assistant, and Emaldo has no public API, no MQTT, no local access. Just a closed mobile app and a cloud they control.

So I decided to reverse-engineer it. And I had the best partner available: Claude, Anthropic's AI coding assistant, running in a terminal on my Mac.

What happened next was one of the most productive — and surprising — days I've had as a developer.

## Starting Point: An APK and Curiosity

The starting point was simple: download the Emaldo Android app (APK), and see what's inside.

I'd already done some preliminary work — decompiling the APK with `jadx`, scanning for BLE UUIDs, noting the API endpoints. I had a markdown file of findings and a Python BLE scanner script ready to go.

I opened Claude Code and said: *"I would like to connect to Emaldo. Let's try BT first."*

## Act 1: Bluetooth — The Quick Win

The BLE exploration went smoothly. Claude scanned for nearby devices, found one advertising UUID `bcf25cee` — which matched a UUID from the decompiled APK. We connected.

Silence. The device accepted our JSON commands but didn't respond.

Back to the APK. Claude dug into the decompiled Java, tracing through obfuscated class names like `com.dinsafer.module_bmt.vd.a`. And there it was — the BLE communication was **AES-256-CBC encrypted** with hardcoded keys:

```
IV:  dfcf28d0734569a6
Key: fbade9e36a3f36d3d676c1b808451dd7
```

One line of encryption code later, we sent `{"cmd": "get_version"}` encrypted, and back came:

```json
{"cmd": "get_version", "result": "v2.24.7", "status": 1}
```

The device was talking to us. First blood.

But the BLE interface turned out to be for WiFi provisioning only — no real-time power data. For that, we needed the cloud.

## Act 2: The Cloud API — RC4 and Snappy

The decompiled APK revealed a REST API at `api.emaldo.com`. The transport used **RC4 encryption** and **Snappy compression** — every request and response encrypted with the app's secret key.

Claude extracted the key from the APK, implemented the encryption, and we logged in:

```json
{"token": "uid_fa107d6b846e97bb159483d1f6ecfe5d", "uid": "ylenius"}
```

From there, we enumerated homes, discovered devices, and found the stats API on `dp.emaldo.com`. Within minutes we had solar production, battery charge/discharge, and grid power — at 5-minute resolution.

This was good enough for a basic Home Assistant integration. We built one: config flow, data coordinator, sensor entities. Pushed it to GitHub. Installed it on HA via SSH.

But 5-minute resolution felt sluggish. The Emaldo app updates in real-time. There had to be a faster channel.

## Act 3: The E2E Protocol — Down the Rabbit Hole

The APK contained references to "E2E" — an end-to-end protocol using something called "MSCT" over "KCP" (a reliable UDP protocol). The code was deeply obfuscated: classes named `s0.k`, `x.n`, `q0.b`. Methods named with Unicode characters that JADX couldn't even display.

Claude traced through thousands of lines of decompiled Java, building a mental model of the protocol stack: UDP → KCP → MSCT binary framing → AES encryption → JSON commands. The E2E login endpoint returned cryptographic credentials: `end_id`, `end_secret`, `chat_secret`, `group_id`.

We tried connecting. KCP packets went out. The server acknowledged them at the transport level. But no application-level response came back.

Hours of debugging. Different encryption keys. Different message formats. The server kept accepting our packets and returning... nothing useful.

## Act 4: The Packet Capture — Truth From the Wire

This is where I had an Android emulator running. We installed the Emaldo app, started `tcpdump` on the emulator, and captured real traffic.

The capture revealed something we'd gotten completely wrong: **the protocol wasn't KCP at all**. It was raw MSCT binary frames sent as plain UDP datagrams. No KCP framing whatsoever.

And the method codes in the OPTION_METHOD field weren't the string names like "alive" we expected from the Java source — they were **2-byte binary integers**. The handshake used string methods ("alive", "heartbeat") but the actual commands used binary codes like `0x30A0`.

We also discovered that the method codes in the wire protocol were **byte-swapped** compared to what appeared in the APK source code. APK code `0xA030` became wire code `0x30A0`. This one detail had been silently breaking everything.

## Act 5: The Encryption Revelation

Even with the correct packet format, commands returned error code `21204`. For hours.

The breakthrough came from a single experiment — trying different encryption keys for different message types. The APK had two encryption classes, `n0.a` and `n0.b`, each using different keys:

- **`end_secret`** — for authenticating with the relay server (alive messages)
- **`chat_secret`** — for communicating with the actual device (heartbeat + commands)

We'd been using `end_secret` for everything. The moment we switched the heartbeat to use `chat_secret`:

```
← method=heartbeat status=0
```

Success. And then the commands started flowing.

## Act 6: Decoding the Data

The `currentflow` command (`0x30A0`) returned 22 bytes of binary data. But what did the bytes mean?

I opened the Emaldo app on my phone and read values off the screen: *Solar 4.8 kW, Grid 3 kW export, Battery 0, Load 1.8 kW.*

Claude queried the device via E2E at the same time. We cross-referenced the binary response with the known values:

```
Bytes: 00 00 30 00 e1 ff ef ff 00 00 00 00 ...
       batt  solar grid  load  other vehicle

Solar:   48 (×0.1 = 4.8 kW)  ✓
Grid:   -31 (×0.1 = -3.1 kW export)  ✓
Load:   -17 (×0.1 = 1.7 kW)  ✓
Battery:  0  ✓
```

All dashboard values from a single command. Signed 16-bit integers in hectowatts.

## Act 7: Home Assistant — Real-Time

With the protocol fully decoded, we rebuilt the HA integration to use E2E instead of REST polling. Real-time power data updating every 10 seconds. Battery SoC. Energy sensors for the Energy Dashboard.

The integration maintains a persistent UDP connection with periodic keepalive messages. When the session expires (the relay server has a ~3 minute timeout without keepalive), it automatically reconnects with fresh credentials.

I watched the sensors populate in Home Assistant, cross-referenced them with the Emaldo app, and with my external grid meter (Talo3P). The values matched.

From sealed APK to working Home Assistant integration with real-time E2E protocol — in one day.

## What I Learned

**Packet captures beat decompilation.** We spent hours studying obfuscated Java to understand the protocol, but 30 seconds of captured traffic from the real app revealed that our fundamental assumption (KCP framing) was wrong. Always validate against reality.

**AI is genuinely useful for reverse engineering.** Claude held the entire context — thousands of lines of decompiled Java, protocol specifications, binary data formats, multiple encryption layers — and could trace connections between obfuscated classes that would take a human hours to follow. It's like pair-programming with someone who has perfect recall.

**Two encryption keys, two purposes.** The most subtle bug was using the wrong key for the wrong message type. The APK code was there all along, but the class names (`n0.a` vs `n0.b`) gave no hint about which key was for which purpose. Only by systematically trying combinations did we find the answer.

**Byte-swapping is evil.** Method code `0xA030` in the Java source becomes `0x30A0` on the wire. This was never documented anywhere — we had to discover it by matching captured packets to APK code.

## The Result

The integration is open source at [github.com/pylenius/ha-emaldo](https://github.com/pylenius/ha-emaldo). It provides:

- **6 real-time power sensors** (10-second updates via E2E/UDP)
  - Solar, Grid, Battery, Load, Vehicle power + Battery SoC
- **6 daily energy sensors** (5-minute updates via REST API)
  - Solar, Grid import/export, Battery charge/discharge, Load energy
- Full API documentation of the reverse-engineered protocol

If you have an Emaldo system and want it in Home Assistant — it just works now.

---

*Built with Claude Code running Opus 4.6. The full reverse engineering session — from BLE scanning to working HA integration — took approximately 12 hours of continuous work. The AI held context across BLE protocols, AES/RC4 encryption, binary protocol framing, Android APK decompilation, asyncio UDP networking, and Home Assistant integration patterns simultaneously.*

*And this was just Opus 4.6 — a general-purpose model that happens to be good at coding. Anthropic recently [previewed Claude Mythos](https://red.anthropic.com/2026/mythos-preview/), a model specifically built for security research under Project Glasswing. Mythos can reconstruct source code from stripped binaries, discover zero-day vulnerabilities in thoroughly audited codebases (it found flaws up to 27 years old in OpenBSD and FreeBSD), and autonomously chain multiple exploits — achieving 181 successful Firefox exploits where its predecessor managed 2. It reversed closed-source binaries, identified vulnerabilities in the reconstructed code, and human security researchers validated 98% of its severity assessments.*

*What we did here — decompiling an APK, tracing obfuscated Java, cracking a proprietary binary protocol with two layers of AES encryption — was a fun afternoon project with a general-purpose AI. With Mythos, this kind of reverse engineering would be trivially easy. The interesting question isn't whether AI can break proprietary protocols. It's what that means for every IoT vendor shipping "security by obscurity" as their strategy.*

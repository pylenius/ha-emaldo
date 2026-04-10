# Emaldo Home Assistant Integration

Custom Home Assistant integration for [Emaldo](https://emaldo.com) battery storage and solar inverter systems (Power Core, Power Store, Power Sense, etc.).

## Features

- Real-time power monitoring (updated every 60 seconds)
- Solar production (per-string and total)
- Battery charge/discharge power
- Grid import/export power
- Home load (grid and backup circuits)
- Auto-discovery of all devices in your Emaldo account

## Supported Devices

- Power Core 2.0 (PC1-BAK15-HS10)
- Power Core 3.0 (PC3)
- Power Store (PS1-BAK10-HS10)
- Power Sense (PSE1, PSE2)
- HP5000 / HP5001

## Installation

### HACS (Recommended)

1. Add this repository as a custom repository in HACS
2. Install "Emaldo" from HACS
3. Restart Home Assistant
4. Go to Settings > Devices & Services > Add Integration > Emaldo
5. Enter your Emaldo app email and password

### Manual

1. Copy `custom_components/emaldo/` to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Go to Settings > Devices & Services > Add Integration > Emaldo

## Sensors

| Sensor | Description | Unit |
|--------|-------------|------|
| Solar power | Total solar production | kW |
| Solar string 1 | MPPT string 1 power | kW |
| Solar string 2 | MPPT string 2 power | kW |
| Battery charge power | Battery charging rate | kW |
| Battery discharge power | Battery discharging rate | kW |
| Battery grid charge power | Grid-to-battery charging rate | kW |
| Grid export power | Power exported to grid | kW |
| Grid import power | Power imported from grid | kW |
| Grid load power | Load powered by grid | kW |
| Backup load power | Load powered by battery/solar | kW |

## How It Works

This integration communicates with the Emaldo cloud API (`api.emaldo.com`) using the same protocol as the official Emaldo mobile app. The API uses RC4 encryption with Snappy compression for data transport.

No local network access or BLE connection is required — all data is fetched from the cloud.

## Requirements

- An Emaldo account (same credentials as the Emaldo mobile app)
- Your Emaldo device must be online and connected to WiFi

## Credits

Protocol reverse-engineered from the Emaldo Android app (Dinsafer platform).

## License

MIT

"""Constants for the Emaldo integration."""

DOMAIN = "emaldo"

# App-level keys (extracted from public APK, same for all users)
APP_ID = "CXRqKjx2MzSAkdyucR9NDyPiiQR2vQcQ"
APP_SECRET = "FpF4Uqiio9k8p9VUSX36UZxy9wLs7ybT"

API_DOMAIN = "api.emaldo.com"
STATS_DOMAIN = "dp.emaldo.com"

# Known device models
ALL_PROVIDERS = [
    "HP5000",
    "HP5001",
    "PC1-BAK15-HS10",
    "PS1-BAK10-HS10",
    "VB1-BAK5-HS10",
    "PC3",
    "PSE1",
    "PSE2",
]

CONF_EMAIL = "email"
CONF_PASSWORD = "password"

DEFAULT_SCAN_INTERVAL = 60  # seconds

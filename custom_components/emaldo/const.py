"""Constants for the Emaldo integration."""

DOMAIN = "emaldo"

APP_ID = "CXRqKjx2MzSAkdyucR9NDyPiiQR2vQcQ"
APP_SECRET = "FpF4Uqiio9k8p9VUSX36UZxy9wLs7ybT"

API_DOMAIN = "api.emaldo.com"
STATS_DOMAIN = "dp.emaldo.com"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"

ALL_PROVIDERS = [
    "HP5000", "HP5001", "PC1-BAK15-HS10", "PS1-BAK10-HS10",
    "VB1-BAK5-HS10", "PC3", "PSE1", "PSE2",
]

DEFAULT_SCAN_INTERVAL = 10   # seconds (E2E real-time power)
ENERGY_SCAN_INTERVAL = 300   # seconds (REST stats for daily energy)

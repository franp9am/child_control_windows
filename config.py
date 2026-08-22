import json
import os
from pathlib import Path

# Every local account may read and write here, so nothing in it is trusted.
SHARED_DIR = Path(r"C:\ProgramData\ScreenTimeShared")
REDEEM_FILE_PATH = SHARED_DIR / "extra_time.txt"  # the child pastes redeem codes in
REMAINING_TIME_FILE_PATH = SHARED_DIR / "remaining_time.txt"  # read by the widget

# Not visible from the child's account.
DATA_DIR = Path(__file__).parent / "data"
USED_CODES_FILE = DATA_DIR / "used_redeem_codes.json"
TARGET_USER_FILE = DATA_DIR / "target_user.txt"  # the child's account, written by install.ps1
CRASH_LOG_FILE = DATA_DIR / "crash.log"

# Hex, 8 bytes or more, written by the installer; the parent's machine needs the same one.
SECRET_FILE = DATA_DIR / "secret.txt"

# The parent's server, e.g. "https://screentime.example.com"; empty disables all syncing.
SERVER_URL = ""
DEVICE_TOKEN_FILE = DATA_DIR / "device_token.txt"  # from add_device.py on the server
APPLIED_GRANTS_FILE = DATA_DIR / "applied_grants.json"
SYNC_TIMEOUT_SECONDS = 5  # a slow server must not stall the check loop

CHECK_INTERVAL_SECONDS = 60
SHUTDOWN_DELAY_SECONDS = 300  # grace period once the time is up
NIGHT_SHUTDOWN_DELAY_SECONDS = 10  # grace period outside the allowed hours
STARTUP_DELAY_SECONDS = 60  # wait after boot before the first check

# Read these through get_config(), never directly: the OVERRIDE_FILE may override them.
SETTINGS = {
    "DAILY_LIMIT_SECONDS": {
        "default": 1 * 60 * 60,
        "allowed": range(24 * 60 * 60 + 1)
    },
    "CARRYOVER": {
        "default": True,
        "allowed": (True, False)
    },
    "MAX_CARRYOVER_SECONDS": {
        "default": 5 * 60 * 60,
        "allowed": range(7 * 24 * 60 * 60 + 1)
    },
    "EARLIEST_HOUR_INCLUDED": {
        "default": 6,
        "allowed": range(24)
    },
    "LATEST_HOUR_INCLUDED": {
        "default": 20,
        "allowed": range(24)
    },
}
OVERRIDE_FILE = DATA_DIR / "override_config.json"

SIGNATURE_CHARS = 4  # changing it invalidates codes already handed out
MAX_REDEEM_FILE_BYTES = 128


def load_overrides() -> dict:
    try:
        stored = json.loads(OVERRIDE_FILE.read_text(encoding="utf-8"))
    except Exception:  # whatever the file holds, the monitor's tick must go on
        return {}
    return stored if isinstance(stored, dict) else {}


def default_settings() -> dict:
    return {name: setting["default"] for name, setting in SETTINGS.items()}


def get_config() -> dict:
    """The settings in force: the defaults, with the override file on top."""
    settings = default_settings()
    settings.update(load_overrides())
    return settings


def save_overrides(sent: dict) -> dict:
    """Store `sent` as the complete override set and return the settings now in force."""
    overrides = {name: value for name, value in sent.items()
                 if name in SETTINGS and value in SETTINGS[name]["allowed"]}
    resulting = {**default_settings(), **overrides}
    # an unusable window would shut the machine down before a correction could arrive
    if resulting["EARLIEST_HOUR_INCLUDED"] > resulting["LATEST_HOUR_INCLUDED"]:
        overrides.pop("EARLIEST_HOUR_INCLUDED", None)
        overrides.pop("LATEST_HOUR_INCLUDED", None)
    tmp_file = OVERRIDE_FILE.with_suffix(".tmp")
    tmp_file.write_text(json.dumps(overrides, indent=2), encoding="utf-8")
    os.replace(tmp_file, OVERRIDE_FILE)  # atomic
    return get_config()

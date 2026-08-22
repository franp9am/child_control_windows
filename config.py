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

# The server may change these too, so read them through get_config(), never as config.NAME.
DEFAULT_SETTINGS = {
    "DAILY_LIMIT_SECONDS": 60 * 60,
    # if False, nothing rolls over and a redeemed code counts only for that day
    "CARRYOVER": True,
    # ceiling on what a fresh day inherits, so a month off is not a month of screen time
    "MAX_CARRYOVER_SECONDS": 5 * 60 * 60,
    "EARLIEST_HOUR_INCLUDED": 6,
    "LATEST_HOUR_INCLUDED": 20,
}
OVERRIDE_FILE = DATA_DIR / "override_config.json"

# What the server may set each of them to; the paths above and SERVER_URL stay local.
ALLOWED_VALUES = {
    "DAILY_LIMIT_SECONDS": range(24 * 60 * 60 + 1),
    "CARRYOVER": (True, False),
    "MAX_CARRYOVER_SECONDS": range(7 * 24 * 60 * 60 + 1),
    "EARLIEST_HOUR_INCLUDED": range(24),
    "LATEST_HOUR_INCLUDED": range(24),
}

SIGNATURE_CHARS = 4  # changing it invalidates codes already handed out
MAX_REDEEM_FILE_BYTES = 128


def load_overrides() -> dict:
    try:
        stored = json.loads(OVERRIDE_FILE.read_text(encoding="utf-8"))
    except Exception:  # whatever the file holds, the monitor's tick must go on
        return {}
    return stored if isinstance(stored, dict) else {}


def get_config() -> dict:
    """The settings in force: DEFAULT_SETTINGS, with the override file on top."""
    settings = dict(DEFAULT_SETTINGS)
    settings.update(load_overrides())
    return settings


def save_overrides(sent: dict) -> dict:
    """Store what the server sent and return the settings now in force."""
    in_force = get_config()
    update = {name: value for name, value in sent.items()
              if name in ALLOWED_VALUES and value in ALLOWED_VALUES[name]}
    earliest = update.get("EARLIEST_HOUR_INCLUDED", in_force["EARLIEST_HOUR_INCLUDED"])
    latest = update.get("LATEST_HOUR_INCLUDED", in_force["LATEST_HOUR_INCLUDED"])
    # an unusable window would shut the machine down before a correction could arrive
    if earliest > latest:
        update.pop("EARLIEST_HOUR_INCLUDED", None)
        update.pop("LATEST_HOUR_INCLUDED", None)

    overrides = load_overrides()
    overrides.update(update)
    tmp_file = OVERRIDE_FILE.with_suffix(".tmp")
    tmp_file.write_text(json.dumps(overrides, indent=2), encoding="utf-8")
    os.replace(tmp_file, OVERRIDE_FILE)  # atomic
    return get_config()

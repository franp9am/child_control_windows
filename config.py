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
CHILD_TOKEN_FILE = DATA_DIR / "child_token.txt"  # from add_child.py on the server
APPLIED_GRANTS_FILE = DATA_DIR / "applied_grants.json"
SYNC_TIMEOUT_SECONDS = 5  # a slow server must not stall the check loop

CHECK_INTERVAL_SECONDS = 60
SHUTDOWN_DELAY_SECONDS = 180  # grace period once the time is up
NIGHT_SHUTDOWN_DELAY_SECONDS = 120  # grace period outside the allowed hours
STARTUP_DELAY_SECONDS = 40  # wait after boot before the first check
NETWORK_WARMUP_SECONDS = 20

# Read these through get_config(), never directly: SETTINGS_FILE holds what is in force,
# and these are only what a machine starts with and falls back to.
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
SETTINGS_FILE = DATA_DIR / "settings.json"  # every setting in force, written by the monitor

SIGNATURE_CHARS = 4  # changing it invalidates codes already handed out
MAX_REDEEM_FILE_BYTES = 128


def default_settings() -> dict:
    return {name: setting["default"] for name, setting in SETTINGS.items()}


def value_allowed(name: str, value) -> bool:
    allowed = SETTINGS[name]["allowed"]
    if isinstance(allowed, range):
        # bool is an int subclass: without the exclusion, True would pass as 1
        return isinstance(value, int) and not isinstance(value, bool) and value in allowed
    elif isinstance(allowed, tuple):
        return type(value) is type(allowed[0]) and value in allowed
    else:
        # an "allowed" spec this function doesn't handle is a bug in SETTINGS;
        # dropping the value keeps the monitor ticking
        return False


def validated_settings(stored: dict) -> dict:
    """Every setting, taking each valid stored value and the default for the rest."""
    settings = default_settings()
    settings.update({name: value for name, value in stored.items()
                     if name in SETTINGS and value_allowed(name, value)})
    # an unusable window would shut the machine down before a correction could arrive
    if settings["EARLIEST_HOUR_INCLUDED"] > settings["LATEST_HOUR_INCLUDED"]:
        settings["EARLIEST_HOUR_INCLUDED"] = SETTINGS["EARLIEST_HOUR_INCLUDED"]["default"]
        settings["LATEST_HOUR_INCLUDED"] = SETTINGS["LATEST_HOUR_INCLUDED"]["default"]
    return settings


def stored_settings() -> dict:
    try:
        stored = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:  # whatever the file holds, the monitor's tick must go on
        return {}
    return stored if isinstance(stored, dict) else {}


def get_config() -> dict:
    """The settings in force: the file, with the default for anything it lacks."""
    return validated_settings(stored_settings())


def write_settings_file(settings: dict) -> None:
    tmp_file = SETTINGS_FILE.with_suffix(".tmp")
    tmp_file.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    os.replace(tmp_file, SETTINGS_FILE)  # atomic


def save_settings(sent: dict) -> dict:
    """Store what the server sent, dropping anything it may not set, and return
    the settings now in force."""
    settings = validated_settings(sent)
    write_settings_file(settings)
    return settings


def ensure_settings_file() -> None:
    """A machine that has never had one starts from the defaults above."""
    if not SETTINGS_FILE.is_file():
        write_settings_file(default_settings())

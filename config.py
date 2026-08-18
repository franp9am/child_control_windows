from pathlib import Path

TARGET_USER = "elias"  # as it shows up in `query user`

# The child writes redeem codes into this one, so it lives in their own profile.
REDEEM_FILE_PATH = Path(r"C:\Users\Elias\Desktop\extra_time.txt")

# Published for remaining_time_widget.py. install.ps1 leaves this folder readable
# by everyone but writable only by SYSTEM, so the child cannot fake the display.
REMAINING_TIME_FILE_PATH = Path(r"C:\ProgramData\ScreenTimeWidget\remaining_time.txt")

# Not visible from the child's account.
DATA_DIR = Path(__file__).parent / "data"
USED_CODES_FILE = DATA_DIR / "used_redeem_codes.json"
CRASH_LOG_FILE = DATA_DIR / "crash.log"

# Shared secret (hex) for signing redeem codes, at least 8 bytes = 16 hex
# characters. It is kept out of this file, which is tracked in git; the
# installer asks for the value and writes it. The parent's machine needs the
# same secret, either in that file or in the CHILD_SECRET env var.
SECRET_FILE = DATA_DIR / "secret.txt"

# Parent's server, e.g. "https://screentime.example.com". Empty disables all
# remote syncing; the machine then runs purely on the local limit and the
# signed redeem codes.
SERVER_URL = ""
DEVICE_TOKEN_FILE = DATA_DIR / "device_token.txt"  # from add_device.py on the server
APPLIED_GRANTS_FILE = DATA_DIR / "applied_grants.json"
SYNC_TIMEOUT_SECONDS = 5  # a slow server must not stall the check loop

CARRYOVER = True  # if False, leftover/unused time never rolls to the next day
# and redeemed codes only count for the day they're redeemed on.

DAILY_LIMIT_SECONDS = 60 * 60
CHECK_INTERVAL_SECONDS = 60
SHUTDOWN_DELAY_SECONDS = 300  # grace period once the time is up
NIGHT_SHUTDOWN_DELAY_SECONDS = 10  # grace period outside the allowed hours
STARTUP_DELAY_SECONDS = 60  # wait after boot before the first check

EARLIEST_HOUR_INCLUDED = 6
LATEST_HOUR_INCLUDED = 20

SIGNATURE_CHARS = 4  # changing it invalidates codes already handed out
MAX_REDEEM_FILE_BYTES = 128


def load_secret() -> bytes:
    """The key redeem codes are signed with; empty when missing or malformed."""
    try:
        with open(SECRET_FILE, "r", encoding="utf-8") as f:
            return bytes.fromhex(f.read().strip())
    except Exception:
        return b""

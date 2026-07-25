from pathlib import Path

TARGET_USER = "elias"  # as it shows up in `query user`

# Reachable from the child's account; C:\Users\Public is readable by everyone.
REDEEM_FILE_PATH = Path(r"C:\Users\Elias\Desktop\extra_time.txt")
REMAINING_TIME_FILE_PATH = Path(r"C:\Users\Elias\Desktop\remaining_time.txt")

# Shared secret (hex) for signing redeem codes -- must be the same here and on
# the parent's machine (create_code.py). At least 8 bytes = 16 hex characters;
SECRET_HEX = ""

# Not visible from the child's account.
DATA_DIR = Path(__file__).parent / "data"
USED_CODES_FILE = DATA_DIR / "used_redeem_codes.json"
CRASH_LOG_FILE = DATA_DIR / "crash.log"

CARRYOVER = True  # if False, leftover/unused time never rolls to the next day
# and redeemed codes only count for the day they're redeemed on.

EXACT_DATE_CHECK = False  # if True, a code's embedded date must match today's
# real calendar date, or it's rejected as invalid.

DAILY_LIMIT_SECONDS = 60 * 60
CHECK_INTERVAL_SECONDS = 60
SHUTDOWN_DELAY_SECONDS = 300  # grace period once the time is up
NIGHT_SHUTDOWN_DELAY_SECONDS = 10  # grace period outside the allowed hours
STARTUP_DELAY_SECONDS = 60  # wait after boot before the first check

EARLIEST_HOUR_INCLUDED = 6
LATEST_HOUR_INCLUDED = 20

SIGNATURE_CHARS = 4  # changing it invalidates codes already handed out
MAX_REDEEM_FILE_BYTES = 128

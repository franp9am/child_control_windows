"""
All settings for monitor.py, remaining_time_widget.py and create_code.py.

Plain python, so keep the quotes and the r"..." prefixes on the windows
paths intact -- a syntax error here stops monitor.py from starting.
"""

from pathlib import Path

TARGET_USER = "elias"  # as it shows up in `query user`

# Reachable from the child's account; C:\Users\Public is readable by everyone.
REDEEM_FILE_PATH = Path(r"C:\Users\Elias\Desktop\extra_time.txt")
REMAINING_TIME_FILE_PATH = Path(r"C:\Users\Elias\Desktop\remaining_time.txt")

# Not visible from the child's account.
DATA_DIR = Path(__file__).parent / "data"
SECRET_FILE = DATA_DIR / "sec.txt"
USED_CODES_FILE = DATA_DIR / "used_redeem_codes.json"

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

# Overlay
POLL_INTERVAL_MS = 5000
MARGIN_PX = 20
OPACITY = 0.85
FONT_FAMILY = "Segoe UI"
FONT_SIZE = 14
WARNING_SECONDS = 15 * 60  # orange below this
CRITICAL_SECONDS = 5 * 60  # red below this
COLOR_NORMAL = "#2ecc71"
COLOR_WARNING = "#f39c12"
COLOR_CRITICAL = "#e74c3c"

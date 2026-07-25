"""
Use this on parents machine to create a code with extra time for the child
"""

import argparse
import datetime
import hashlib
import hmac
import os

from config import SECRET_HEX, SIGNATURE_CHARS

# The secret must equal the one in config.py on the child's machine. The
# CHILD_SECRET env var overrides config.py if set.
sec = os.environ.get("CHILD_SECRET", SECRET_HEX)
try:
    secret = bytes.fromhex(sec.strip())
except ValueError:
    secret = b""
if not secret:
    raise ValueError(
        "Set SECRET_HEX in config.py (or the CHILD_SECRET env var) "
        "to the shared secret used on the child's machine"
    )


def get_code(extra_sec=3600, date=None):
    if not isinstance(extra_sec, int):
        raise ValueError("extra_sec should be an int")

    if date is None:
        date = datetime.date.today().isoformat()

    # The date is a nonce that keeps each code unique; it is part of the signed
    # payload and is only validated against the real calendar on redemption if
    # EXACT_DATE_CHECK is enabled in config.py.
    payload = f"{date}:{extra_sec}"
    sign = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sign[:SIGNATURE_CHARS]}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a code with extra seconds")
    parser.add_argument(
        "--extra_sec",
        "-e",
        type=int,
        default=3600,
        help="Extra seconds (default: 3600)",
    )
    parser.add_argument(
        "--date",
        "-d",
        type=str,
        default=None,
        help="Nonce date (default: today, e.g. 2026-07-23). "
        "Override to issue a second code of the same amount on the same day.",
    )

    args = parser.parse_args()

    print(get_code(extra_sec=args.extra_sec, date=args.date))

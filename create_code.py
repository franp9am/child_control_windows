"""
Use this on parents machine to create a code with extra time for the child
"""

import argparse
import datetime
import hashlib
import hmac
import os

from config import SECRET_FILE, SIGNATURE_CHARS

# make sure the secret is set and is equal to the on in childs computed monitor.py script
sec = os.environ.get("CHILD_SECRET")
if sec is None:
    try:
        with open(SECRET_FILE, "r") as f:
            sec = f.read().strip()
    except FileNotFoundError:
        pass

if sec is None:
    raise ValueError(f"CHILD_SECRET is not set and {SECRET_FILE} not found")

secret = bytes.fromhex(sec)


def get_code(extra_sec=3600, date=None):
    if not isinstance(extra_sec, int):
        raise ValueError("extra_sec should be an int")

    if date is None:
        date = datetime.date.today().isoformat()

    # The date is a nonce that keeps each code unique; it is part of the signed
    # payload but is not validated against the real calendar on redemption.
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

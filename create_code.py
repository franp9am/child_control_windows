"""
Use this on parents machine to create a code with extra time for the child
"""

import argparse
import datetime
import hashlib
import hmac
import os


# make sure the secret is set and is equal to the on in childs computed monitor.py script
if os.environ["CHILD_SECRET"] is None:
    raise ValueError("CHILD_SECRET is not set")


sec = os.environ["CHILD_SECRET"]
secret = bytes.fromhex(sec)


def get_code(date_str=None, extra_sec=3600):
    if date_str is None:
        date_str = datetime.datetime.now().date().isoformat()
    if not isinstance(date_str, str):
        raise ValueError("date_str should be a string")
    if not isinstance(extra_sec, int):
        raise ValueError("extra_sec should be an int")

    payload = f"{date_str}:{extra_sec}"
    sign = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sign[:4]}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a code with date string and extra seconds"
    )
    parser.add_argument(
        "--date_str",
        "-d",
        type=str,
        help="Date string in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--extra_sec",
        "-e",
        type=int,
        default=3600,
        help="Extra seconds (default: 3600)",
    )

    args = parser.parse_args()

    print(
        get_code(
            date_str=args.date_str,
            extra_sec=args.extra_sec,
        ),
    )

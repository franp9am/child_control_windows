"""
Use this on parents machine to create a code with extra time for the child
"""

import argparse
import hashlib
import hmac
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

# make sure the secret is set and is equal to the on in childs computed monitor.py script
sec = os.environ.get("CHILD_SECRET")
if sec is None:
    try:
        with open(DATA_DIR / "sec.txt", "r") as f:
            sec = f.read().strip()
    except FileNotFoundError:
        pass

if sec is None:
    raise ValueError("CHILD_SECRET is not set and data/sec.txt not found")

secret = bytes.fromhex(sec)


def get_code(extra_sec=3600):
    if not isinstance(extra_sec, int):
        raise ValueError("extra_sec should be an int")

    payload = f"{extra_sec}"
    sign = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sign[:4]}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a code with extra seconds")
    parser.add_argument(
        "--extra_sec",
        "-e",
        type=int,
        default=3600,
        help="Extra seconds (default: 3600)",
    )

    args = parser.parse_args()

    print(get_code(extra_sec=args.extra_sec))

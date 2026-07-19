"""
Use this on parents machine to create a code with extra time for the child
"""

import argparse
import hashlib
import hmac
import os


# make sure the secret is set and is equal to the on in childs computed monitor.py script
if os.environ["CHILD_SECRET"] is None:
    raise ValueError("CHILD_SECRET is not set")


sec = os.environ["CHILD_SECRET"]
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

"""
Use this on the child's machine to monitor the time
and shutdown the machine when the time is up.

This script should be run on startup and not be accessible
from the childs account.
"""

import datetime
import hashlib
import hmac
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

TARGET_USER = "elias"  # change this to the target user
REDEEM_FILE_PATH = (
    r"C:\Users\Public\eli_redeem_time.txt"  # change this to the redeem file path
)

DAILY_LIMIT_SECONDS = 120 * 60
CHECK_INTERVAL_SECONDS = 60
SHUTDOWN_DELAY_SECONDS = 300

EARLIEST_HOUR_INCLUDED = 6
LATEST_HOUR_INCLUDED = 20

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TAKE_CHARS = 4  # 65 536 different signatures for redeem codes


try:
    with open(DATA_DIR / "sec.txt", "r") as f:  # path with secret password
        SECRET = bytes.fromhex(f.read().strip())
except Exception as e:
    print(f"Error loading secret: {e}")
    SECRET = b""


def get_datafile():
    return DATA_DIR / (datetime.date.today().isoformat() + ".json")


def check_time():
    hour = datetime.datetime.now().hour
    return EARLIEST_HOUR_INCLUDED <= hour <= LATEST_HOUR_INCLUDED


def load_data(datafile):
    try:
        with open(datafile, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "time_spent_sec": 0,
            "ticks": [],
            "last_tick": None,
            "extra_time_sec": 0,
            "event_log": [],
            "used_redeem_codes": [],
        }


def save_data(data, datafile):
    # make the write atomic to prevent random breakage
    tmp_file = datafile.with_suffix(".tmp")
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_file, datafile)  # make the write atomic


def query_users():
    r = subprocess.run(
        ["query", "user"], capture_output=True, text=True, errors="ignore"
    )

    try:
        return r.stdout
    except Exception:
        return ""


def user_logged_in(user=TARGET_USER):
    return user.lower() in query_users().lower()


def shutdown_machine(shutdown_delay_seconds=SHUTDOWN_DELAY_SECONDS):
    # Force close apps and power off; add a small delay if you want a warning.
    args = ["shutdown", "/s", "/f", "/t", str(int(shutdown_delay_seconds))]
    try:
        subprocess.run(
            args, check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    except Exception:
        pass


def send_message(message):
    subprocess.run(["msg", "*", message])


def verify(msg: bytes, sig_hex: str) -> bool:
    expected = hmac.new(SECRET, msg, hashlib.sha256).hexdigest()[:TAKE_CHARS]
    return expected == sig_hex


def handle_redeem_file() -> Optional[int]:
    """Checks the redeem code from file and adds the time to the data file"""
    if not len(SECRET):  # if secret is not loaded, program should not break
        return {
            "status": "cannot load secret",
            "redeem_code": None,
            "extra_time_sec": 0,
        }

    if not Path(REDEEM_FILE_PATH).is_file():
        return {
            "status": "no_file",
            "redeem_code": None,
            "extra_time_sec": 0,
        }
    # prevent an attack with loading large files
    if os.path.getsize(REDEEM_FILE_PATH) > 128:
        return {
            "status": "file too large",
            "redeem_code": None,
            "extra_time_sec": 0,
        }
    try:
        with open(REDEEM_FILE_PATH) as f:
            redeem_content = f.read().strip()
    except Exception:
        return {
            "status": "cannot read file",
            "redeem_code": None,
            "extra_time_sec": 0,
        }

    if not redeem_content:
        return {
            "status": "empty file",
            "redeem_code": None,
            "extra_time_sec": 0,
        }

    if not isinstance(redeem_content, str):
        return {
            "status": "cannot read file",
            "redeem_code": None,
            "extra_time_sec": 0,
        }

    parts = redeem_content.split(":")
    # we expect three parts in the format: date:extra_time:signature
    if not len(parts) == 3:
        return {
            "status": "invalid format",
            "redeem_code": redeem_content,
            "extra_time_sec": 0,
        }

    req_date = parts[0]
    try:
        req_extra_time = int(parts[1])  # trying to convert to integer
    except Exception:
        return {
            "status": "invalid format",
            "redeem_code": redeem_content,
            "extra_time_sec": 0,
        }

    req_sig = parts[2]
    extracted_payload = f"{req_date}:{req_extra_time}".encode()

    if not req_date == datetime.date.today().isoformat():
        return {
            "status": "invalid date",
            "redeem_code": redeem_content,
            "extra_time_sec": 0,
        }

    if not verify(extracted_payload, req_sig):
        return {
            "status": "invalid signature",
            "redeem_code": redeem_content,
            "extra_time_sec": 0,
        }

    return {
        "status": "valid",
        "redeem_code": redeem_content,
        "extra_time_sec": req_extra_time,
    }


def main():
    time.sleep(60)  # wait for the redeem file to be created
    while True:
        now = datetime.datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        datafile = get_datafile()
        data = load_data(datafile)

        is_logged_in = user_logged_in()

        if is_logged_in:
            if not check_time():
                send_message(message="Night time")
                data["event_log"].append(f"Night time {now_str}")
                save_data(data, datafile)
                shutdown_machine(shutdown_delay_seconds=10)
                return

            redeem = handle_redeem_file()
            if (
                redeem
                and redeem["status"] == "valid"
                and not (redeem["redeem_code"] in data["used_redeem_codes"])
            ):
                # redeem code is valid and not used yet
                data["used_redeem_codes"].append(redeem["redeem_code"])
                extra_time = redeem["extra_time_sec"]
                data["event_log"].append(f"redeem code {extra_time} {now_str}")
                data["extra_time_sec"] += extra_time
                send_message(message=f"extra time {extra_time}")
                save_data(data, datafile)

            if data["time_spent_sec"] >= DAILY_LIMIT_SECONDS + data["extra_time_sec"]:
                send_message(message="time up")
                data["event_log"].append(f"time up {now_str}")
                save_data(data, datafile)
                shutdown_machine(shutdown_delay_seconds=SHUTDOWN_DELAY_SECONDS)
                return

            data["time_spent_sec"] += CHECK_INTERVAL_SECONDS
            data["ticks"].append(now_str)
            data["last_tick"] = now_str
            save_data(data, datafile)
        else:
            # not logged in, nothing to report
            pass

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

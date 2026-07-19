"""
Use this on the child's machine to monitor the time
and shutdown the machine when the time is up.

This script should be run on startup under system account 
and not be accessible from the childs account.
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

USED_CODES_FILE = DATA_DIR / "used_redeem_codes.json"

TAKE_CHARS = 4  # 65 536 different signatures for redeem codes


try:
    with open(DATA_DIR / "sec.txt", "r") as f:  # path with secret password
        SECRET = bytes.fromhex(f.read().strip())
except Exception as e:
    print(f"Error loading secret: {e}")
    SECRET = b""


def get_datafile():
    return DATA_DIR / (datetime.date.today().isoformat() + ".json")


def find_previous_datafile(today: datetime.date) -> Optional[Path]:
    """Find the most recent data file for a date before today, if any."""
    prev_dates = []
    for p in DATA_DIR.glob("*.json"):
        try:
            d = datetime.date.fromisoformat(p.stem)
        except ValueError:
            continue
        if d < today:
            prev_dates.append(d)
    if not prev_dates:
        return None
    return DATA_DIR / (max(prev_dates).isoformat() + ".json")


def compute_carryover_sec(today: datetime.date) -> int:
    """
    Time to carry into today: leftover unused time from the most recent
    previous day with data, plus one full DAILY_LIMIT_SECONDS for every
    calendar day in between that has no data file at all (not connected).
    """
    prev_file = find_previous_datafile(today)
    if prev_file is None:
        return 0
    prev_date = datetime.date.fromisoformat(prev_file.stem)
    prev_data = load_data(prev_file)
    leftover = max(
        0,
        DAILY_LIMIT_SECONDS
        + prev_data.get("extra_time_sec", 0)
        - prev_data.get("time_spent_sec", 0),
    )
    missing_days = (today - prev_date).days - 1  # fully skipped days, no file
    return leftover + missing_days * DAILY_LIMIT_SECONDS


def check_not_night_time():
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
        }


def save_data(data, datafile):
    # make the write atomic to prevent random breakage
    tmp_file = datafile.with_suffix(".tmp")
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_file, datafile)  # make the write atomic


def load_used_codes():
    """Redeem codes are no longer tied to a date, so used codes must be
    tracked across days rather than in the per-day data file."""
    try:
        with open(USED_CODES_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_used_codes(used_codes):
    tmp_file = USED_CODES_FILE.with_suffix(".tmp")
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(sorted(used_codes), f, indent=2)
    os.replace(tmp_file, USED_CODES_FILE)  # make the write atomic


def query_users():
    """May only work on windows Pro"""
    r = subprocess.run(
        ["query", "user"],
        capture_output=True,
        text=True,
        errors="ignore"
    )
    return r.stdout


def user_has_tasks(user):
    """Should also work on windows Home"""
    cmd = f'tasklist /V | findstr /I "{user}"'
    r = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        errors="ignore"
    )
    return r.returncode == 0 and bool(r.stdout.strip())


def user_logged_in(user=TARGET_USER):
    try:
        qu = query_users().lower()
        return user.lower() in qu
    except Exception:  # query user doesnt work or doesnt return a string
        return user_has_tasks(user)


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
    """May only work on windows Pro"""
    try:
        subprocess.run(["msg", "*", message])
    except Exception:
        # not critical
        pass


def verify(msg: bytes, sig_hex: str) -> bool:
    expected = hmac.new(SECRET, msg, hashlib.sha256).hexdigest()[:TAKE_CHARS]
    return expected == sig_hex


def handle_redeem_file():
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
    # we expect two parts in the format: extra_time:signature
    if not len(parts) == 2:
        return {
            "status": "invalid format",
            "redeem_code": redeem_content,
            "extra_time_sec": 0,
        }

    try:
        req_extra_time = int(parts[0])  # trying to convert to integer
    except Exception:
        return {
            "status": "invalid format",
            "redeem_code": redeem_content,
            "extra_time_sec": 0,
        }

    req_sig = parts[1]
    extracted_payload = f"{req_extra_time}".encode()

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
        is_new_day = not datafile.is_file()
        data = load_data(datafile)

        if is_new_day:
            carryover = compute_carryover_sec(now.date())
            if carryover > 0:
                data["extra_time_sec"] = carryover
                data["event_log"].append(f"carryover {carryover} sec from previous day {now_str}")
                save_data(data, datafile)

        is_logged_in = user_logged_in()

        if is_logged_in:
            if not check_not_night_time():
                send_message(message="Night time")
                data["event_log"].append(f"Night time {now_str}")
                save_data(data, datafile)
                shutdown_machine(shutdown_delay_seconds=10)
                return

            redeem = handle_redeem_file()
            if redeem and redeem["status"] == "valid":
                used_codes = load_used_codes()
                if redeem["redeem_code"] not in used_codes:
                    # redeem code is valid and not used yet
                    used_codes.add(redeem["redeem_code"])
                    save_used_codes(used_codes)
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

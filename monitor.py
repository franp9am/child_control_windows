"""
Use this on the child's machine to monitor the time
and shutdown the machine when the time is up.

This script should be run on startup under system account
and not be accessible from the childs account.

All settings live in config.py next to this file.
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

from config import (
    CARRYOVER,
    CHECK_INTERVAL_SECONDS,
    DAILY_LIMIT_SECONDS,
    DATA_DIR,
    EARLIEST_HOUR_INCLUDED,
    EXACT_DATE_CHECK,
    LATEST_HOUR_INCLUDED,
    MAX_REDEEM_FILE_BYTES,
    NIGHT_SHUTDOWN_DELAY_SECONDS,
    REDEEM_FILE_PATH,
    REMAINING_TIME_FILE_PATH,
    SECRET_FILE,
    SHUTDOWN_DELAY_SECONDS,
    SIGNATURE_CHARS,
    STARTUP_DELAY_SECONDS,
    TARGET_USER,
    USED_CODES_FILE,
)

DATA_DIR.mkdir(parents=True, exist_ok=True)

try:
    with open(SECRET_FILE, "r") as f:  # path with secret password
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
    """Leftover time from the last day with data, plus a full daily limit for
    every calendar day in between that has no data file (machine was off)."""
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


def is_night_time():
    hour = datetime.datetime.now().hour
    return not (EARLIEST_HOUR_INCLUDED <= hour <= LATEST_HOUR_INCLUDED)


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
    tmp_file = datafile.with_suffix(".tmp")
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_file, datafile)  # atomic, prevents random breakage


def load_used_codes():
    """Codes are not tied to a date, so used ones are tracked across days."""
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


def write_remaining_time_file(remaining_sec):
    """Publish remaining seconds to a child-readable file for a UI to display."""
    target = REMAINING_TIME_FILE_PATH
    tmp_file = target.with_suffix(".tmp")
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(str(max(0, remaining_sec)))
        os.replace(tmp_file, target)
    except Exception:
        pass  # not critical


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
    expected = hmac.new(SECRET, msg, hashlib.sha256).hexdigest()[:SIGNATURE_CHARS]
    return expected == sig_hex


def handle_redeem_file():
    """Checks the redeem code from file and adds the time to the data file"""
    if not len(SECRET):  # if secret is not loaded, program should not break
        return {
            "status": "cannot load secret",
            "redeem_code": None,
            "extra_time_sec": 0,
        }

    if not REDEEM_FILE_PATH.is_file():
        try:
            REDEEM_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
            REDEEM_FILE_PATH.touch()
        except Exception:
            pass
        return {
            "status": "no_file",
            "redeem_code": None,
            "extra_time_sec": 0,
        }
    # prevent an attack with loading large files
    if os.path.getsize(REDEEM_FILE_PATH) > MAX_REDEEM_FILE_BYTES:
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
    # The date is a signed nonce that keeps otherwise-identical codes distinct.
    # It's only checked against the real calendar if EXACT_DATE_CHECK is set.
    extracted_payload = f"{req_date}:{req_extra_time}".encode()

    if not verify(extracted_payload, req_sig):
        return {
            "status": "invalid signature",
            "redeem_code": redeem_content,
            "extra_time_sec": 0,
        }

    if EXACT_DATE_CHECK and req_date != datetime.date.today().isoformat():
        return {
            "status": "date mismatch",
            "redeem_code": redeem_content,
            "extra_time_sec": 0,
        }

    return {
        "status": "valid",
        "redeem_code": redeem_content,
        "extra_time_sec": req_extra_time,
    }


def ensure_datafile(datafile, now):
    """Create today's datafile if it doesn't exist yet, applying carryover if
    configured; otherwise just load what's already there."""
    if datafile.is_file():
        return load_data(datafile)
    data = load_data(datafile)  # defaults, since the file doesn't exist
    if CARRYOVER:
        carryover = compute_carryover_sec(now.date())
        if carryover > 0:
            data["extra_time_sec"] = carryover
            now_str = now.strftime("%Y-%m-%d %H:%M:%S")
            data["event_log"].append(f"carryover {carryover} sec from previous day {now_str}")
    save_data(data, datafile)
    return data


def main():
    # publish the remaining time immediately, before the startup delay, so a
    # stale value from yesterday isn't shown even for the first minute
    data = ensure_datafile(get_datafile(), datetime.datetime.now())
    write_remaining_time_file(DAILY_LIMIT_SECONDS + data["extra_time_sec"] - data["time_spent_sec"])

    time.sleep(STARTUP_DELAY_SECONDS)  # wait for the redeem file to be created

    while True:
        now = datetime.datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        datafile = get_datafile()
        data = ensure_datafile(datafile, now)

        is_logged_in = user_logged_in()

        if is_logged_in:
            if is_night_time():
                send_message(message="Night time")
                data["event_log"].append(f"Night time {now_str}")
                save_data(data, datafile)
                write_remaining_time_file(0)
                shutdown_machine(NIGHT_SHUTDOWN_DELAY_SECONDS)
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

            limit = DAILY_LIMIT_SECONDS + data["extra_time_sec"]
            if data["time_spent_sec"] >= limit:
                send_message(message="time up")
                data["event_log"].append(f"time up {now_str}")
                save_data(data, datafile)
                write_remaining_time_file(0)
                shutdown_machine(shutdown_delay_seconds=SHUTDOWN_DELAY_SECONDS)
                return

            data["time_spent_sec"] += CHECK_INTERVAL_SECONDS
            data["ticks"].append(now_str)
            data["last_tick"] = now_str
            save_data(data, datafile)
            remaining = limit - data["time_spent_sec"]
            write_remaining_time_file(remaining)
        else:
            # not logged in, nothing to report
            pass

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

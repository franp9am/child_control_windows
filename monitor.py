import datetime
import hashlib
import hmac
import json
import os
import subprocess
import time
import traceback
from pathlib import Path
from typing import Optional

import config
import remote_sync
from config import (
    CHECK_INTERVAL_SECONDS,
    CRASH_LOG_FILE,
    DATA_DIR,
    MAX_REDEEM_FILE_BYTES,
    NIGHT_SHUTDOWN_DELAY_SECONDS,
    REDEEM_FILE_PATH,
    REMAINING_TIME_FILE_PATH,
    SECRET_FILE,
    SERVER_URL,
    SHUTDOWN_DELAY_SECONDS,
    SIGNATURE_CHARS,
    STARTUP_DELAY_SECONDS,
    TARGET_USER_FILE,
    USED_CODES_FILE,
)

DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_secret() -> bytes:
    """The key redeem codes are signed with; empty when missing or malformed."""
    try:
        return bytes.fromhex(SECRET_FILE.read_text(encoding="utf-8").strip())
    except Exception:  # runs at import, where nothing would catch a raise
        return b""


SECRET = load_secret()  # empty without a secret file: codes stop being accepted

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"  # shared by every stamp written and read
TICK_TIME_FORMAT = "%H:%M:%S"  # ticks live in a per-date file, so no date needed


def get_datafile(now):
    return DATA_DIR / (now.date().isoformat() + ".json")


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


def compute_carryover_sec(today: datetime.date, settings) -> int:
    """Leftover time from the last day with data, plus a full daily limit for
    every calendar day in between that has no data file (machine was off),
    capped at MAX_CARRYOVER_SECONDS."""
    prev_file = find_previous_datafile(today)
    if prev_file is None:
        return 0
    prev_date = datetime.date.fromisoformat(prev_file.stem)
    prev_data = load_data(prev_file)
    leftover = max(0, remaining_seconds(prev_data, settings))
    missing_days = (today - prev_date).days - 1  # fully skipped days, no file
    return min(
        leftover + missing_days * settings["DAILY_LIMIT_SECONDS"],
        settings["MAX_CARRYOVER_SECONDS"],
    )


def is_night_time(now, settings):
    return not (
        settings["EARLIEST_HOUR_INCLUDED"] <= now.hour <= settings["LATEST_HOUR_INCLUDED"]
    )


def load_data(datafile):
    # A file that parses but is missing keys (or isn't a dict at all) must not
    # crash the loop, so defaults fill in whatever is absent.
    data = {
        "time_spent_sec": 0,
        "ticks": [],
        "last_tick": None,
        "carryover_sec": 0,
        "granted_sec": 0,
        "event_log": [],
    }
    try:
        with open(datafile, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            data.update(loaded)
    except Exception:
        pass
    return data


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


def remaining_seconds(data, settings):
    return (
        settings["DAILY_LIMIT_SECONDS"]
        + data["carryover_sec"]
        + data["granted_sec"]
        - data["time_spent_sec"]
    )


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


def log_unexpected_error():
    """Append the current traceback to the crash log; never raise itself."""
    try:
        now_str = datetime.datetime.now().strftime(TIMESTAMP_FORMAT)
        with open(CRASH_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"--- {now_str} ---\n{traceback.format_exc()}\n")
    except Exception:
        pass


def load_target_user() -> str:
    """The child's account, as install.ps1 wrote it; there is no default."""
    try:
        name = TARGET_USER_FILE.read_text(encoding="utf-8-sig").strip()
    except OSError:
        name = ""
    if not name:
        raise ValueError(f"No child account in {TARGET_USER_FILE}; run install.ps1 to set it")
    return name


try:
    TARGET_USER = load_target_user()
except Exception:
    log_unexpected_error()  # a failure this early leaves no other trace
    raise


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
    # The date is a signed nonce that keeps otherwise-identical codes distinct;
    # it is not checked against the calendar, so a code has no expiry date.
    extracted_payload = f"{req_date}:{req_extra_time}".encode()

    if not verify(extracted_payload, req_sig):
        return {
            "status": "invalid signature",
            "redeem_code": redeem_content,
            "extra_time_sec": 0,
        }

    # Normalize the code so variants like "0600", "+600" or " 600" (all
    # accepted by int()) count as the same code in the used-codes ledger.
    normalized_code = f"{req_date}:{req_extra_time}:{req_sig}"

    return {
        "status": "valid",
        "redeem_code": normalized_code,
        "extra_time_sec": req_extra_time,
    }


def sync_with_server(data, datafile, now, settings) -> dict:
    """Report today's totals to the parent's server, apply the grants it sends
    back and adopt any settings it sends with them. A server that is down, slow
    or unreachable simply leaves the local numbers and settings untouched.

    Returns the settings to carry on with, which are the ones passed in unless
    the server changed them."""
    if not SERVER_URL:
        return settings
    token = remote_sync.load_device_token()
    if not token:
        return settings

    now_str = now.strftime(TIMESTAMP_FORMAT)
    status = remote_sync.DailyStatus(
        date=now.date().isoformat(),
        time_spent_sec=data["time_spent_sec"],
        carryover_sec=data["carryover_sec"],
        granted_sec=data["granted_sec"],
        remaining_sec=remaining_seconds(data, settings),
        last_tick=data["last_tick"],
        config_overrides=config.load_overrides(),
    )
    already_applied = remote_sync.load_applied_grant_ids()
    try:
        answer = remote_sync.send_status(status, already_applied, token)
    except Exception:
        return settings  # offline is the normal case, not a crash

    # The server keeps sending a grant until it hears the id back, so applying
    # first and recording afterwards can repeat a grant, never lose one.
    for grant in answer.pending_grants:
        data["granted_sec"] += grant.seconds
        data["event_log"].append(f"server grant {grant.seconds} sec id {grant.id} {now_str}")
        send_message(message=f"extra time {grant.seconds}")
    if answer.config_overrides is not None:
        # Stored, so they outlive this run and stay in force while the server
        # is unreachable.
        settings = config.save_overrides(answer.config_overrides)
        # log what survived validation, not what was sent -- they differ on a bad value
        data["event_log"].append(f"server config {config.load_overrides()} {now_str}")
    if answer.pending_grants or already_applied or answer.config_overrides is not None:
        save_data(data, datafile)
        remote_sync.save_applied_grant_ids([grant.id for grant in answer.pending_grants])
    return settings


def ensure_datafile(datafile, now, settings):
    """Create today's datafile if it doesn't exist yet, applying carryover if
    configured; otherwise just load what's already there."""
    if datafile.is_file():
        return load_data(datafile)
    data = load_data(datafile)  # defaults, since the file doesn't exist
    if settings["CARRYOVER"]:
        carryover = compute_carryover_sec(now.date(), settings)
        if carryover > 0:
            data["carryover_sec"] = carryover
            now_str = now.strftime(TIMESTAMP_FORMAT)
            data["event_log"].append(f"carryover {carryover} sec from previous day {now_str}")
    save_data(data, datafile)
    return data


def seconds_to_charge(data, now):
    """Real seconds since the last tick when that gap looks like an ordinary
    tick, otherwise the nominal interval. A tick is one sleep plus its own
    overhead, so anything longer means the machine slept, rebooted or skipped
    ticks -- and anything shorter means the clock moved backwards (DST); none
    of that is time the child spent at the screen."""
    try:
        previous = datetime.datetime.strptime(data["last_tick"], TIMESTAMP_FORMAT)
    except (KeyError, TypeError, ValueError):
        return CHECK_INTERVAL_SECONDS  # no previous tick today
    elapsed = int((now - previous).total_seconds())
    if CHECK_INTERVAL_SECONDS <= elapsed <= 2 * CHECK_INTERVAL_SECONDS:
        return elapsed
    return CHECK_INTERVAL_SECONDS


def main():
    # publish the remaining time immediately, before the startup delay, so a
    # stale value from yesterday isn't shown even for the first minute
    try:
        now = datetime.datetime.now()
        settings = config.get_config()
        data = ensure_datafile(get_datafile(now), now, settings)
        write_remaining_time_file(remaining_seconds(data, settings))
    except Exception:
        log_unexpected_error()

    time.sleep(STARTUP_DELAY_SECONDS)  # wait for the redeem file to be created

    while True:
        # A transient failure (locked file, redeem file vanishing mid-check,
        # odd data on disk) must not kill the monitor: log it, skip this tick
        # and try again, instead of leaving the machine unrestricted.
        try:
            now = datetime.datetime.now()
            now_str = now.strftime(TIMESTAMP_FORMAT)
            datafile = get_datafile(now)
            settings = config.get_config()
            data = ensure_datafile(datafile, now, settings)

            is_logged_in = user_logged_in()

            if is_logged_in:
                if is_night_time(now, settings):
                    # enforce first; bookkeeping below may fail without
                    # cancelling the shutdown
                    shutdown_machine(NIGHT_SHUTDOWN_DELAY_SECONDS)
                    write_remaining_time_file(0)
                    send_message(message="Night time")
                    data["event_log"].append(f"Night time {now_str}")
                    save_data(data, datafile)
                    sync_with_server(data, datafile, now, settings)
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
                        data["granted_sec"] += extra_time
                        send_message(message=f"extra time {extra_time}")
                        save_data(data, datafile)

                settings = sync_with_server(data, datafile, now, settings)

                if remaining_seconds(data, settings) <= 0:
                    # enforce first; bookkeeping below may fail without
                    # cancelling the shutdown
                    shutdown_machine(shutdown_delay_seconds=SHUTDOWN_DELAY_SECONDS)
                    write_remaining_time_file(0)
                    send_message(message="time up")
                    data["event_log"].append(f"time up {now_str}")
                    save_data(data, datafile)
                    # last word before the process exits: without it the page
                    # keeps yesterday's numbers and the grant that caused this
                    # shutdown stays pending until the next boot
                    sync_with_server(data, datafile, now, settings)
                    return

                data["time_spent_sec"] += seconds_to_charge(data, now)
                data["ticks"].append(now.strftime(TICK_TIME_FORMAT))
                data["last_tick"] = now_str
                save_data(data, datafile)
                write_remaining_time_file(remaining_seconds(data, settings))
            else:
                # Nothing is being spent, but keep publishing: the widget treats
                # a file that stops being refreshed as "the monitor is gone".
                write_remaining_time_file(remaining_seconds(data, settings))
        except Exception:
            log_unexpected_error()

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

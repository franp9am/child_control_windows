import csv
import io
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import db

# The page is read by the family, not by whoever happens to host it, so the
# rendered times must not depend on the server process's own timezone.
DISPLAY_TIMEZONE = ZoneInfo("Europe/Prague")


class SyncRequest(BaseModel):
    date: str
    time_spent_sec: int
    carryover_sec: int
    granted_sec: int
    remaining_sec: int
    last_tick: str | None
    applied_grant_ids: list[int]


class PendingGrant(BaseModel):
    id: int
    seconds: int


class SyncResponse(BaseModel):
    pending_grants: list[PendingGrant]


@dataclass
class User:
    id: int
    login: str
    family_id: int


@dataclass
class GrantView:
    minutes: int
    created: str
    granted_by: str


@dataclass
class LastSeenView:
    synced: str
    remaining: str


@dataclass
class DayUsage:
    weekday: str
    spent: str
    bar_percent: int
    is_today: bool


@dataclass
class WeekUsage:
    days: list[DayUsage]
    total: str


def formatted_local_time(utc_timestamp: str) -> str:
    local = datetime.fromisoformat(utc_timestamp).astimezone(DISPLAY_TIMEZONE)
    return local.strftime("%Y-%m-%d %H:%M")


def duration_in_words(seconds: int) -> str:
    """Negative means the child is past the limit, e.g. after a negative grant."""
    hours, minutes = divmod(abs(seconds) // 60, 60)
    if hours == 0 and minutes == 0:
        return "no time left"
    magnitude = f"{hours} h {minutes} min" if hours else f"{minutes} min"
    return magnitude if seconds > 0 else f"{magnitude} over"


def compact_duration(seconds: int) -> str:
    hours, minutes = divmod(seconds // 60, 60)
    if seconds <= 0:
        return "0"
    if hours == 0:
        return f"{minutes}m"
    return f"{hours}h{minutes:02d}"


def percent_of_tallest(seconds: int, tallest: int) -> int:
    """Any use at all gets at least a sliver, so a short day is not an empty column."""
    if seconds == 0:
        return 0
    return max(round(100 * seconds / tallest), 1)


def last_week(connection: sqlite3.Connection, device_id: int) -> WeekUsage:
    """Time spent on each of the last seven days, oldest first; missing days count as zero."""
    today = datetime.now(DISPLAY_TIMEZONE).date()
    days = [today - timedelta(days=offset) for offset in reversed(range(7))]
    rows = connection.execute(
        """SELECT date, time_spent_sec FROM status
           WHERE device_id = :device_id AND date >= :first_day""",
        {"device_id": device_id, "first_day": days[0].isoformat()},
    ).fetchall()
    spent_on = {row["date"]: row["time_spent_sec"] for row in rows}
    seconds_per_day = [max(spent_on.get(day.isoformat(), 0), 0) for day in days]
    # An hour is the shortest scale, so a quiet week doesn't look like a busy one.
    tallest = max(max(seconds_per_day), 3600)
    return WeekUsage(
        days=[
            DayUsage(
                weekday=day.strftime("%a"),
                spent=compact_duration(seconds),
                bar_percent=percent_of_tallest(seconds, tallest),
                is_today=day == today,
            )
            for day, seconds in zip(days, seconds_per_day)
        ],
        total=compact_duration(sum(seconds_per_day)),
    )


def last_seen(connection: sqlite3.Connection, device_id: int) -> LastSeenView | None:
    row = connection.execute(
        """SELECT remaining_sec, updated_at FROM status
           WHERE device_id = :device_id
           ORDER BY date DESC
           LIMIT 1""",
        {"device_id": device_id},
    ).fetchone()
    if row is None:
        return None
    return LastSeenView(
        synced=formatted_local_time(row["updated_at"]),
        remaining=duration_in_words(row["remaining_sec"]),
    )


def pending_grants(connection: sqlite3.Connection, device_id: int) -> list[GrantView]:
    rows = connection.execute(
        """SELECT grants.seconds, grants.created_at, users.login FROM grants
           JOIN users ON users.id = grants.granted_by
           WHERE grants.device_id = :device_id AND grants.acked_at IS NULL
           ORDER BY grants.id DESC""",
        {"device_id": device_id},
    ).fetchall()
    return [
        GrantView(
            minutes=row["seconds"] // 60,
            created=formatted_local_time(row["created_at"]),
            granted_by=row["login"],
        )
        for row in rows
    ]


def csv_download(filename: str, header: list[str], rows: list[list]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def export_filename(device_name: str, table: str) -> str:
    """Device names are free text, so keep only what is safe in a header and a filename."""
    return f"{re.sub(r'[^A-Za-z0-9]+', '-', device_name).strip('-') or 'device'}-{table}.csv"


def devices_in_family(connection: sqlite3.Connection, family_id: int) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT id, name FROM devices WHERE family_id = :family_id ORDER BY id",
        {"family_id": family_id},
    ).fetchall()


def require_device_in_family(
    connection: sqlite3.Connection, device_id: int, family_id: int
) -> sqlite3.Row:
    """A device belonging to another family is indistinguishable from one that does not exist."""
    device = connection.execute(
        "SELECT id, name FROM devices WHERE id = :device_id AND family_id = :family_id",
        {"device_id": device_id, "family_id": family_id},
    ).fetchone()
    if device is None:
        raise HTTPException(status_code=404, detail="unknown device")
    return device


db.create_schema()

app = FastAPI()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def current_user(request: Request) -> User:
    """The only place that knows how a person proves who they are.

    nginx does the authenticating and passes the name it verified; swapping it
    for a session cookie or an identity provider means rewriting this function
    and nothing else. The app must therefore never be reachable except through
    the proxy, which overwrites the header on every request.
    """
    login = request.headers.get("x-remote-user", "")
    if not login:
        raise HTTPException(status_code=403, detail="request did not come through the proxy")
    connection = db.connect()
    user = connection.execute(
        "SELECT id, login, family_id FROM users WHERE login = :login", {"login": login}
    ).fetchone()
    connection.close()
    if user is None:
        raise HTTPException(status_code=403, detail=f"no account for {login}")
    return User(id=user["id"], login=user["login"], family_id=user["family_id"])


def authenticated_device_id(authorization: str) -> int:
    scheme, _, token = authorization.partition(" ")
    if scheme != "Bearer" or not token:
        raise HTTPException(status_code=401, detail="missing bearer token")
    connection = db.connect()
    device = connection.execute(
        "SELECT id FROM devices WHERE token = :token", {"token": token}
    ).fetchone()
    connection.close()
    if device is None:
        raise HTTPException(status_code=401, detail="unknown token")
    return device["id"]


@app.post("/api/sync")
def sync(http_request: Request, sync_request: SyncRequest) -> SyncResponse:
    device_id = authenticated_device_id(http_request.headers.get("authorization", ""))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    connection = db.connect()
    with connection:
        connection.execute(
            """INSERT INTO status (device_id, date, time_spent_sec, carryover_sec,
                                   granted_sec, remaining_sec, last_tick, updated_at)
               VALUES (:device_id, :date, :time_spent_sec, :carryover_sec,
                       :granted_sec, :remaining_sec, :last_tick, :updated_at)
               ON CONFLICT (device_id, date) DO UPDATE SET
                   time_spent_sec = :time_spent_sec,
                   carryover_sec = :carryover_sec,
                   granted_sec = :granted_sec,
                   remaining_sec = :remaining_sec,
                   last_tick = :last_tick,
                   updated_at = :updated_at""",
            {
                "device_id": device_id,
                "date": sync_request.date,
                "time_spent_sec": sync_request.time_spent_sec,
                "carryover_sec": sync_request.carryover_sec,
                "granted_sec": sync_request.granted_sec,
                "remaining_sec": sync_request.remaining_sec,
                "last_tick": sync_request.last_tick,
                "updated_at": now,
            },
        )
        connection.executemany(
            """UPDATE grants SET acked_at = :now
               WHERE id = :grant_id AND device_id = :device_id AND acked_at IS NULL""",
            [
                {"now": now, "grant_id": grant_id, "device_id": device_id}
                for grant_id in sync_request.applied_grant_ids
            ],
        )
        pending = connection.execute(
            """SELECT id, seconds FROM grants
               WHERE device_id = :device_id AND acked_at IS NULL
               ORDER BY id""",
            {"device_id": device_id},
        ).fetchall()
    connection.close()
    return SyncResponse(
        pending_grants=[PendingGrant(id=row["id"], seconds=row["seconds"]) for row in pending]
    )


@app.get("/health")
def health() -> dict[str, str]:
    connection = db.connect()
    connection.execute("SELECT count(*) FROM devices").fetchone()
    connection.close()
    return {"status": "ok"}


@app.get("/")
def index(request: Request, device_id: int | None = None) -> HTMLResponse:
    user = current_user(request)
    connection = db.connect()
    devices = devices_in_family(connection, user.family_id)
    selected_device = next(
        (device for device in devices if device["id"] == device_id),
        devices[0] if devices else None,
    )
    if selected_device is None:
        waiting, status, week = [], None, None
    else:
        waiting = pending_grants(connection, selected_device["id"])
        status = last_seen(connection, selected_device["id"])
        week = last_week(connection, selected_device["id"])
    connection.close()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "user": user,
            "devices": devices,
            "selected_device": selected_device,
            "pending_grants": waiting,
            "last_seen": status,
            "week": week,
        },
    )


@app.post("/grants")
async def create_grant(request: Request) -> RedirectResponse:
    user = current_user(request)
    form = await request.form()
    try:
        device_id = int(form["device_id"])
        seconds = int(form["minutes"]) * 60
    except (KeyError, ValueError):
        raise HTTPException(status_code=400, detail="device_id and minutes must be whole numbers")
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    connection = db.connect()
    try:
        require_device_in_family(connection, device_id, user.family_id)
        with connection:
            connection.execute(
                """INSERT INTO grants (device_id, granted_by, seconds, created_at)
                   VALUES (:device_id, :granted_by, :seconds, :created_at)""",
                {
                    "device_id": device_id,
                    "granted_by": user.id,
                    "seconds": seconds,
                    "created_at": created_at,
                },
            )
    finally:
        connection.close()
    target = request.url_for("index").include_query_params(device_id=device_id)
    return RedirectResponse(str(target), status_code=303)


@app.get("/export/grants")
def export_grants(request: Request, device_id: int) -> Response:
    user = current_user(request)
    connection = db.connect()
    try:
        device_name = require_device_in_family(connection, device_id, user.family_id)["name"]
        rows = connection.execute(
            """SELECT grants.id, grants.seconds, grants.created_at, grants.acked_at, users.login
               FROM grants
               JOIN users ON users.id = grants.granted_by
               WHERE grants.device_id = :device_id
               ORDER BY grants.id""",
            {"device_id": device_id},
        ).fetchall()
    finally:
        connection.close()
    zone = DISPLAY_TIMEZONE.key
    return csv_download(
        filename=export_filename(device_name, "grants"),
        header=["id", "minutes", "granted by", f"created ({zone})", f"applied ({zone})"],
        rows=[
            [
                row["id"],
                row["seconds"] // 60,
                row["login"],
                formatted_local_time(row["created_at"]),
                formatted_local_time(row["acked_at"]) if row["acked_at"] else "",
            ]
            for row in rows
        ],
    )


@app.get("/export/screen-time")
def export_screen_time(request: Request, device_id: int) -> Response:
    user = current_user(request)
    connection = db.connect()
    try:
        device_name = require_device_in_family(connection, device_id, user.family_id)["name"]
        rows = connection.execute(
            """SELECT date, time_spent_sec, carryover_sec, granted_sec, remaining_sec,
                      last_tick, updated_at
               FROM status
               WHERE device_id = :device_id
               ORDER BY date""",
            {"device_id": device_id},
        ).fetchall()
    finally:
        connection.close()
    zone = DISPLAY_TIMEZONE.key
    return csv_download(
        filename=export_filename(device_name, "screen-time"),
        header=[
            "date",
            "time_spent_sec",
            "carryover_sec",
            "granted_sec",
            "remaining_sec",
            "last_tick (device clock)",
            f"synced ({zone})",
        ],
        rows=[
            [
                row["date"],
                row["time_spent_sec"],
                row["carryover_sec"],
                row["granted_sec"],
                row["remaining_sec"],
                row["last_tick"] or "",
                formatted_local_time(row["updated_at"]),
            ]
            for row in rows
        ],
    )

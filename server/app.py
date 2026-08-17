import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import db


class SyncRequest(BaseModel):
    date: str
    time_spent_sec: int
    extra_time_sec: int
    remaining_sec: int
    last_tick: str | None
    applied_grant_ids: list[int]


class PendingGrant(BaseModel):
    id: int
    seconds: int


class SyncResponse(BaseModel):
    pending_grants: list[PendingGrant]


@dataclass
class GrantView:
    minutes: int
    created: str


@dataclass
class LastSeenView:
    synced: str
    remaining: str


def formatted_local_time(utc_timestamp: str) -> str:
    return datetime.fromisoformat(utc_timestamp).astimezone().strftime("%Y-%m-%d %H:%M")


def duration_in_words(seconds: int) -> str:
    if seconds <= 0:
        return "no time left"
    hours, minutes = divmod(seconds // 60, 60)
    if hours:
        return f"{hours} h {minutes} min"
    return f"{minutes} min"


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
        """SELECT seconds, created_at FROM grants
           WHERE device_id = :device_id AND acked_at IS NULL
           ORDER BY id DESC""",
        {"device_id": device_id},
    ).fetchall()
    return [
        GrantView(
            minutes=row["seconds"] // 60,
            created=formatted_local_time(row["created_at"]),
        )
        for row in rows
    ]


db.create_schema()

app = FastAPI()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


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
            """INSERT INTO status (device_id, date, time_spent_sec, extra_time_sec, remaining_sec,
                                   last_tick, updated_at)
               VALUES (:device_id, :date, :time_spent_sec, :extra_time_sec, :remaining_sec,
                       :last_tick, :updated_at)
               ON CONFLICT (device_id, date) DO UPDATE SET
                   time_spent_sec = :time_spent_sec,
                   extra_time_sec = :extra_time_sec,
                   remaining_sec = :remaining_sec,
                   last_tick = :last_tick,
                   updated_at = :updated_at""",
            {
                "device_id": device_id,
                "date": sync_request.date,
                "time_spent_sec": sync_request.time_spent_sec,
                "extra_time_sec": sync_request.extra_time_sec,
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
    connection = db.connect()
    devices = connection.execute("SELECT id, name FROM devices ORDER BY name").fetchall()
    selected_device = next(
        (device for device in devices if device["id"] == device_id),
        devices[0] if devices else None,
    )
    if selected_device is None:
        waiting, status = [], None
    else:
        waiting = pending_grants(connection, selected_device["id"])
        status = last_seen(connection, selected_device["id"])
    connection.close()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "devices": devices,
            "selected_device": selected_device,
            "pending_grants": waiting,
            "last_seen": status,
        },
    )


@app.post("/grants")
async def create_grant(request: Request) -> RedirectResponse:
    form = await request.form()
    try:
        device_id = int(form["device_id"])
        seconds = int(form["minutes"]) * 60
    except (KeyError, ValueError):
        raise HTTPException(status_code=400, detail="device_id and minutes must be whole numbers")
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    connection = db.connect()
    try:
        with connection:
            connection.execute(
                """INSERT INTO grants (device_id, seconds, created_at)
                   VALUES (:device_id, :seconds, :created_at)""",
                {"device_id": device_id, "seconds": seconds, "created_at": created_at},
            )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=404, detail="unknown device")
    finally:
        connection.close()
    return RedirectResponse(f"/?device_id={device_id}", status_code=303)

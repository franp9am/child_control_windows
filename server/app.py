from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
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


db.create_schema()

app = FastAPI()


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

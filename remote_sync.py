"""Talks to the parent's server: reports today's totals, receives time grants.

Nothing here enforces anything -- the monitor keeps counting and shutting the
machine down whether the server answers or not.
"""

import json
import os
import urllib.request
from dataclasses import asdict, dataclass
from typing import List, Optional

from config import (
    APPLIED_GRANTS_FILE,
    DEVICE_TOKEN_FILE,
    SERVER_URL,
    SYNC_TIMEOUT_SECONDS,
)


@dataclass
class DailyStatus:
    """What the parent's page shows about today; sent on every sync."""

    date: str
    time_spent_sec: int
    carryover_sec: int
    granted_sec: int
    remaining_sec: int
    last_tick: Optional[str]


@dataclass
class Grant:
    id: int
    seconds: int


def load_device_token() -> str:
    """Identifies this machine to the server; empty string means not set up.

    Deliberately not the signing secret and not stored in config.py: the server
    keeps a copy of this token, so it must be worthless to whoever holds it --
    it grants no time, it only names the device.
    """
    try:
        with open(DEVICE_TOKEN_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def load_applied_grant_ids() -> List[int]:
    """Grants already added to the data file but not yet confirmed by the server."""
    try:
        with open(APPLIED_GRANTS_FILE, "r", encoding="utf-8") as f:
            return [int(grant_id) for grant_id in json.load(f)]
    except Exception:
        return []


def save_applied_grant_ids(grant_ids):
    tmp_file = APPLIED_GRANTS_FILE.with_suffix(".tmp")
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(sorted(grant_ids), f)
    os.replace(tmp_file, APPLIED_GRANTS_FILE)  # make the write atomic


def request_pending_grants(
    status: DailyStatus, applied_grant_ids: List[int], token: str
) -> List[Grant]:
    """Send today's totals plus the grant ids already applied (which acknowledges
    them), and return the grants the server still considers unapplied.

    Raises on any network, HTTP or protocol problem -- the caller decides.
    """
    payload = asdict(status)
    payload["applied_grant_ids"] = applied_grant_ids
    request = urllib.request.Request(
        SERVER_URL.rstrip("/") + "/api/sync",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=SYNC_TIMEOUT_SECONDS) as response:
        answer = json.load(response)
    return [
        Grant(id=int(grant["id"]), seconds=int(grant["seconds"]))
        for grant in answer["pending_grants"]
    ]

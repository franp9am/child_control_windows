import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("CHILD_CONTROL_DB") or Path(__file__).parent / "data.sqlite")

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    token TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS grants (
    id INTEGER PRIMARY KEY,
    device_id INTEGER NOT NULL REFERENCES devices(id),
    seconds INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    acked_at TEXT
);
CREATE TABLE IF NOT EXISTS status (
    device_id INTEGER NOT NULL REFERENCES devices(id),
    date TEXT NOT NULL,
    time_spent_sec INTEGER NOT NULL,
    extra_time_sec INTEGER NOT NULL,
    last_tick TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (device_id, date)
);
"""


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_schema() -> None:
    connection = connect()
    connection.executescript(SCHEMA)
    connection.commit()
    connection.close()

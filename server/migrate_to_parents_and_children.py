"""One-shot rename of the schema that predates commit b33f917.

devices -> children, users -> parents, and the device_id columns that point at
them. Stop the app before running this: app.py calls create_schema() at import,
so a running server recreates the new tables empty and the rename then fails.
"""

import shutil
import sqlite3
import sys

import db

RENAMES = [
    "ALTER TABLE users RENAME TO parents",
    "ALTER TABLE devices RENAME TO children",
    "ALTER TABLE grants RENAME COLUMN device_id TO child_id",
    "ALTER TABLE status RENAME COLUMN device_id TO child_id",
]


def table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {row["name"] for row in rows}


def main() -> None:
    connection = db.connect()  # PRAGMA foreign_keys = ON, which is what makes
    connection.isolation_level = None  # the FK clauses follow the rename
    existing = table_names(connection)

    if {"parents", "children"} & existing:
        sys.exit(
            f"{db.DB_PATH} already has parents/children -- either it is migrated, "
            "or a running app recreated them empty and you should restore a backup"
        )
    missing = {"users", "devices", "grants", "status"} - existing
    if missing:
        sys.exit(f"{db.DB_PATH} has no {', '.join(sorted(missing))} to migrate")

    backup = db.DB_PATH.parent / (db.DB_PATH.name + ".before-rename")
    shutil.copy2(db.DB_PATH, backup)

    connection.execute("BEGIN")
    for statement in RENAMES:
        connection.execute(statement)
    broken = connection.execute("PRAGMA foreign_key_check").fetchall()
    if broken:
        connection.execute("ROLLBACK")
        sys.exit(f"foreign keys broken after the rename, nothing changed: {broken}")
    connection.execute("COMMIT")

    counts = {
        table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("families", "parents", "children", "grants", "status")
    }
    connection.close()
    print(f"migrated {db.DB_PATH}, backup at {backup}")
    print(", ".join(f"{table} {count}" for table, count in counts.items()))


if __name__ == "__main__":
    main()

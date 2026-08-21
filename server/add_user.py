import sqlite3
import sys

import db


def family_id(connection: sqlite3.Connection, family_name: str) -> int:
    """Families are created on first use: the first parent of a family makes it exist."""
    connection.execute(
        "INSERT OR IGNORE INTO families (name) VALUES (?)", (family_name,)
    )
    return connection.execute(
        "SELECT id FROM families WHERE name = ?", (family_name,)
    ).fetchone()["id"]


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("usage: python add_user.py <login> <family>")
    login, family_name = sys.argv[1], sys.argv[2]
    db.create_schema()
    connection = db.connect()
    try:
        with connection:
            connection.execute(
                "INSERT INTO users (login, family_id) VALUES (?, ?)",
                (login, family_id(connection, family_name)),
            )
    except sqlite3.IntegrityError:
        sys.exit(f"user {login!r} already exists")
    finally:
        connection.close()
    print(f"{login} added to family {family_name}")
    print(f"now give them a password: sudo htpasswd /etc/nginx/htpasswd {login}")


if __name__ == "__main__":
    main()

import secrets
import sqlite3
import sys

import db


MIN_TOKEN_CHARS = 16


def main() -> None:
    if len(sys.argv) not in (3, 4):
        sys.exit("usage: python add_device.py <family> <name> [token]")
    family_name, name = sys.argv[1], sys.argv[2]
    token = sys.argv[3] if len(sys.argv) == 4 else secrets.token_hex(16)
    if len(token) < MIN_TOKEN_CHARS:
        sys.exit(f"token must be at least {MIN_TOKEN_CHARS} characters")
    db.create_schema()
    connection = db.connect()
    family = connection.execute(
        "SELECT id FROM families WHERE name = ?", (family_name,)
    ).fetchone()
    if family is None:
        connection.close()
        sys.exit(f"no family {family_name!r} -- create it with add_user.py")
    try:
        with connection:
            connection.execute(
                "INSERT INTO devices (family_id, name, token) VALUES (?, ?, ?)",
                (family["id"], name, token),
            )
    except sqlite3.IntegrityError:
        sys.exit(f"device {name!r} already exists in family {family_name!r}")
    finally:
        connection.close()
    print(token)


if __name__ == "__main__":
    main()

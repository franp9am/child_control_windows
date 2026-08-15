import secrets
import sqlite3
import sys

import db


MIN_TOKEN_CHARS = 16


def main() -> None:
    if len(sys.argv) not in (2, 3):
        sys.exit("usage: python add_device.py <name> [token]")
    name = sys.argv[1]
    token = sys.argv[2] if len(sys.argv) == 3 else secrets.token_hex(16)
    if len(token) < MIN_TOKEN_CHARS:
        sys.exit(f"token must be at least {MIN_TOKEN_CHARS} characters")
    db.create_schema()
    connection = db.connect()
    try:
        with connection:
            connection.execute("INSERT INTO devices (name, token) VALUES (?, ?)", (name, token))
    except sqlite3.IntegrityError:
        sys.exit(f"device {name!r} already exists")
    finally:
        connection.close()
    print(token)


if __name__ == "__main__":
    main()

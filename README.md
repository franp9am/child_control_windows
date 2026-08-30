# Screen time limit for a child's Windows PC

A daily screen-time limit, a range of allowed hours, and a way to grant extra time.
No cloud account, remote control is optional, can be fully offline.

Simpler to set up than Microsoft Family Safety, simple rules -- no kid surveillance.


## Parts

* `monitor.py` -- runs as SYSTEM from boot, counts the child's session time, shuts the
  machine down when the limit is used up or the allowed hours end.
* `config.py` -- every setting, next to the monitor in a folder the child cannot read.
* `remaining_time_widget.py` -- a small always-on-top "time left" box in the child's
  session. Cosmetic; the child may hide it with Ctrl+Alt+H or kill it.
* `server/` -- optional web page for the parent, to grant time remotely and see usage.

## Setup on the child's machine

1. Give the child a **non-admin** Windows account.
2. Double-click `install.cmd`, or right-click `install.ps1` -> **Run with PowerShell**
   (either way it re-launches itself as admin).
   It asks which local account is the child's, for the shared secret (Enter generates
   one), and optionally for the child token and URL of the parent's server. Then it
   installs Python via winget if needed, copies the monitor into `C:\ProgramData\ScreenTime`
   and locks that folder, puts the widget and an "Extra time" shortcut in the shared
   `C:\ProgramData\ScreenTimeShared`, and registers the two scheduled tasks.
3. Reboot. The monitor runs from boot, the widget appears when the child logs in.

If the installer generated the secret, it prints it at the end -- the parent's machine
needs the same one, in `data/secret.txt` next to `create_code.py` or in `CHILD_SECRET`.

`uninstall.cmd` removes everything (pass `-KeepData` to keep the usage history).

The two `.cmd` files only hand the matching `.ps1` to PowerShell with
`-ExecutionPolicy Bypass`, which is what lets them run on a machine whose default
policy refuses scripts. They change no setting; without them, running `.\install.ps1`
from a prompt fails with "running scripts is disabled on this system".

Upgrading by copying the scripts over is not enough: the monitor refuses to start without
`data\target_user.txt`, which only the installer writes. Run the installer again.

### Safety

The installer does **not** do these, and without them the setup is bypassable:

* password-protect the BIOS, so the machine cannot be booted from another device;
* encrypt the disk with BitLocker, so the drive cannot be read in another machine.

## Settings

All in `config.py`, plain Python, next to the monitor. The ones you are likely to change
are entries of the `SETTINGS` dict, each with its `default` and the `allowed` values it
may take: `DAILY_LIMIT_SECONDS`, `CARRYOVER` (unused time rolls over to the next day),
`MAX_CARRYOVER_SECONDS`, `EARLIEST_HOUR_INCLUDED` and `LATEST_HOUR_INCLUDED`.

The rest are ordinary variables: paths, the check interval, the shutdown grace periods.
Read settings through `get_config()`, never straight from `SETTINGS` -- values sent by the
server are stored in `data/override_config.json` and win over the defaults. Deleting that
file goes back to `config.py`; it is not meant to be edited by hand.

## Extra time

Two ways, and either works on its own.

**A grant from the server**, if one is set up: the parent enters minutes on the web page
and the monitor picks them up on its next sync, within about a minute. Negative grants
work too, and never outlive the day.

**A signed code**, for when there is no server. The parent runs `create_code.py` and gets
`<date>:<seconds>:<signature>`, e.g. `2026-07-23:3600:a184` for an extra hour. The child
pastes it into `C:\ProgramData\ScreenTimeShared\extra_time.txt` (the "Extra time" shortcut
on the shared desktop). The date is only a nonce, not an expiry -- a code stays valid
forever, but each one can be redeemed exactly once.

`create_code.py` imports nothing else from the project, so copying that one
file to the parent's machine is enough, as long as its `SIGNATURE_CHARS` matches
`config.py` and both machines hold the same secret.

## Optional: the parent's server

FastAPI + SQLite, one page listing the family's children with their usage and a box to
grant time. It never enforces anything -- if it is down, the monitor keeps counting and
shutting down as usual, and grants queue until the machine syncs again.

```
cd server
uv sync
uv run python add_parent.py <login> <family>   # prints the htpasswd line to run next
uv run python add_child.py <family> <name>     # prints the child token for install.ps1
uv run uvicorn app:app --host 127.0.0.1
```

Authentication lives entirely in the reverse proxy in front of it: the proxy checks the
password and passes the verified login to the app in an `X-Remote-User` header, which
decides whose children the page shows. So the app must never be reachable except through
the proxy -- keep it on `127.0.0.1` -- and the proxy must blank that header on anything it
does not authenticate, or a client could name any parent it likes.

The monitor already reports the settings it has in force and applies a `config` key in the
answer, but the server does not send one yet: today it only grants time.

## Python dependencies

None on the child's machine. The server has its own, in `server/pyproject.toml`.

## License

Copyright (c) 2026 Peter Franek. MIT License -- see `LICENSE`.
Use it, change it, sell it; just keep the copyright notice.

# Screen time limit for a child's Windows PC

A daily screen-time limit, a range of allowed hours, and a way to grant extra time.
No cloud account, remote control is optional, can be fully offline.

Simpler to set up than Microsoft Family Safety, simple rules -- no kid surveillance.


## Parts

* `monitor.py` -- runs as SYSTEM from boot, counts the child's session time, shuts the
  machine down when the limit is used up or the allowed hours end. A tick only counts,
  and a shutdown only happens, while the child is logged in with the screen unlocked;
  a locked machine is left alone until somebody unlocks it.
* `config.py` -- every setting, next to the monitor in a folder the child cannot read.
* `remaining_time_widget.py` -- a small always-on-top "time left" box in the child's
  session. Cosmetic; the child may hide it with Ctrl+Alt+H or kill it.
* `server/` -- optional web page for the parent, to grant time remotely and see usage.

## Setup on the child's machine

1. Give the child a **non-admin** Windows account.
2. Double-click `install.cmd`, or right-click `install.ps1` -> **Run with PowerShell**
   (either way it re-launches itself as admin).
   It asks which local account is the child's, for the shared secret (Enter generates
   one), optionally for the child token and URL of the parent's server, and where the
   "Extra time" shortcut goes, probably `C:\Users\<child>\Desktop`.
   Then it installs Python via winget if needed, copies the monitor into
   `C:\ProgramData\ScreenTime` and locks that folder, puts the widget in the shared
   `C:\ProgramData\ScreenTimeShared`, and registers the two scheduled tasks.
3. Reboot. The monitor runs from boot, the widget appears when the child logs in.

If the installer generated the secret, it prints it at the end -- the parent's machine
needs the same one, in `data/secret.txt` next to `grant_extra_time_offline.py` or in
`CHILD_SECRET`.

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

The five settings the monitor obeys live in `data/settings.json`, next to the monitor
where the child cannot read them: `DAILY_LIMIT_SECONDS`, `CARRYOVER` (unused time rolls
over to the next day), `MAX_CARRYOVER_SECONDS`, `EARLIEST_HOUR_INCLUDED` and
`LATEST_HOUR_INCLUDED`. Example:

```json
{
  "DAILY_LIMIT_SECONDS": 3600,
  "CARRYOVER": true,
  "MAX_CARRYOVER_SECONDS": 18000,
  "EARLIEST_HOUR_INCLUDED": 6,
  "LATEST_HOUR_INCLUDED": 20
}
```

One hour a day, usable between 6:00 and 20:59 -- the night starts at 21:00 and ends at
6:00 -- with unused time carried over, but never more than five hours of it.

Edit that file, or let the parent's server set them. Delete it and
the monitor falls back to the defaults in `config.py`, writing the file again at its
next start.

`config.py` holds the rest -- paths, the check interval, the shutdown grace periods -- and,
in its `SETTINGS` dict, the `default` and `allowed` values for the five above. Those
defaults seed `settings.json` on a machine that has none and stand in for any value in it
that is missing or out of range, so a mangled file cannot leave the machine unrestricted.
Read settings through `get_config()`, never straight from `SETTINGS`.

## Extra time

Two ways, and either works on its own.

**A grant from the server**, if one is set up: the parent enters minutes on the web page
and the monitor picks them up on its next sync, within about a minute. Negative grants
work too, and never outlive the day.

A grant carries no date and never expires: it is applied on the day the machine next
syncs, not the day it was made, so one entered while the PC is off lands whenever the
child next turns it on. For a negative grant that also bounds the damage -- it can take
at most that one day's limit and carryover, and the remainder is dropped rather than
carried into the next day, so -20 h and -6 h cost the same single day.

**A signed code**, for when there is no server. The parent runs
`grant_extra_time_offline.py` and gets `<date>:<seconds>:<signature>`, e.g.
`2026-07-23:3600:a184` for an extra hour. The child pastes it into
`C:\ProgramData\ScreenTimeShared\extra_time.txt` (the "Extra time" shortcut the install
put on the desktop). The date is only a nonce, not an expiry -- a code stays valid
forever, but each one can be redeemed exactly once.

`grant_extra_time_offline.py` imports nothing else from the project, so copying that
one file to the parent's machine is enough, as long as its `SIGNATURE_CHARS` matches
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

The monitor reports the settings it has in force in every sync, and the server answers
with the ones it wants whenever the two differ. There is no page for editing them yet: a
change is a row in `settings_changes`, written by hand for now.

## Python dependencies

None on the child's machine. The server has its own, in `server/pyproject.toml`.

## License

Copyright (c) 2026 Peter Franek. MIT License -- see `LICENSE`.
Use it, change it, sell it; just keep the copyright notice.

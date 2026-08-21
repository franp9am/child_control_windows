## About

A simple setup to limit childs screentime on a (typically windows) computer.

It sets up a daily screentime limit and supports allowing more time upon request.

Very basic. Compared to microsoft family safety, it has these advantages:

* Easier to set up
* Independent on cloud, all is fully local
* Works offline


## Quick setup (one click)

For the common case there is now an installer that does every step below for you.

1. Make sure the **child has a non-admin Windows account**.
2. Edit `config.py` first -- at minimum `TARGET_USER` (the child's account name), `DAILY_LIMIT_SECONDS`, and the allowed-hours range. The installer reads its settings from there. The shared secret is **not** in `config.py`, which is tracked in git: the installer asks for it and writes it into the locked data folder. Generate one with, e.g.:
   ```
   python -c "import secrets; print(secrets.token_hex(16))"
   ```
   The parent's machine needs the **same** secret for `create_code.py`, either in its own `data/secret.txt` or in the `CHILD_SECRET` env var.
3. Right-click `install.ps1` -> **Run with PowerShell** (it re-launches itself as admin). It will:
   * install Python 3 machine-wide via winget if it isn't already present,
   * copy `monitor.py`, `remote_sync.py` + `config.py` into `C:\ProgramData\ScreenTime` and lock the folder so the child cannot read it (this is what protects `data\secret.txt`),
   * ask for the shared secret and, optionally, the device token for the parent's server, and write both into the locked folder,
   * copy the overlay widget into `C:\ProgramData\ScreenTimeWidget` (child-readable; the widget is self-contained and gets the remaining-time file path as a task argument, so no config goes there),
   * register a scheduled task running `monitor.py` as SYSTEM at startup,
   * register a scheduled task running the widget in the child's session at their logon.
4. Reboot. The monitor runs from boot; the widget appears when the child logs in.

To remove everything, right-click `uninstall.ps1` -> Run with PowerShell (add `-KeepData` to keep the usage/history files).

**The installer does not do the two BIOS/BitLocker steps in the Safety section** -- those are still manual, and without them the setup is bypassable.

## Manual setup

The step-by-step version, if you prefer to do it by hand or the installer doesn't fit your machine.

* Child needs to have a non-admin account.
* On the admin account, you put the monitor.py script to some folder that is not visible from childs account.
* The monitor.py script is run from python upon machine startup
* To install python, you can do for instance `winget install --id Python.Python.3.11 -e --source winget` in PowerShell
* To find out where python is, you may use `Get-Command python` in PowerShell (or try `which python`)
* Open task scheduler (taskschd.msc) and define a trigger at system startup with the command `C:\path\to\python \path\to\monitor.py`. If you have Windows Home, you may need to do something like 
```
schtasks /create /tn "ScreenTimeMonitor" ^
/tr "\"C:\Path\To\python.exe\" \"C:\Path\To\monitor.py\"" ^
/sc onstart /ru SYSTEM /rl HIGHEST /f
``` 
but I didn't test it.
* Edit `config.py`, which sits next to the scripts and holds every setting. Nothing has to be changed in monitor.py itself. The variables you will care about:
  * `TARGET_USER` -- child's windows account
  * `DAILY_LIMIT_SECONDS` -- how many seconds per day is the maximal screentime
  * `CARRYOVER` -- if `True`, unused time (including unused extra time from redeemed codes) rolls over to the next day; if `False`, each day starts fresh at `DAILY_LIMIT_SECONDS` and a redeemed code only grants extra time for the day it's redeemed
  * `SHUTDOWN_DELAY_SECONDS` -- after system shut down, how many seconds is the grace period (to save things etc)
  * `EARLIEST_HOUR_INCLUDED` and `LATEST_HOUR_INCLUDED` -- range of hours the computer will be usable, for instance 6 and 20, to exclude night time
  * `SECRET_FILE` -- where the shared secret for signing extra-time codes is read from; the value must match the parent's machine
  * `SERVER_URL` -- the parent's server for remote grants, empty to run without one; the device token goes in `DEVICE_TOKEN_FILE`
  * `REDEEM_FILE_PATH` -- path to a local file the children can access, to write a code in case you grant him extra time
  * `DATA_DIR` -- where the per-day json files and the used-code list live

  The rest (poll intervals, the redeem signature length) rarely needs touching. It is ordinary python, so keep the quotes and the `r"..."` prefixes on the windows paths intact -- a syntax error there stops monitor.py from starting.


## Remaining time overlay

`remaining_time_widget.py` shows a small always-on-top "time left" box in the top-right corner of the child's screen. monitor.py publishes the seconds remaining today to `REMAINING_TIME_FILE_PATH` on every tick; the widget only reads that one file and is fully self-contained -- it never touches `config.py` or the locked monitor folder.

Setup, run under the **child's own account** (not SYSTEM):
* Nothing extra to grant — the file lives in `C:\ProgramData\ScreenTimeWidget\` next to the widget script, which the installer leaves readable by all local accounts. Only SYSTEM (i.e. monitor.py) can write there, so the child can read the number but not fake it.
* The widget shows `Time: --` if the file stops being refreshed for more than `STALE_AFTER_SECONDS`, rather than leaving a dead value on screen. A stale `0` is kept as "Time's up", since monitor.py writes it and then exits to shut the machine down.
* The widget takes the remaining-time file path as its first command-line argument (the installer fills it in from config.py's `REMAINING_TIME_FILE_PATH`); without an argument it falls back to the default at the top of the script. Colours, font and poll interval are in the same block.
* Put a shortcut to it in the child's Startup folder (`shell:startup`), targeting `pythonw.exe` (not `python.exe`, so no console window appears), e.g.
```
C:\Path\To\pythonw.exe C:\Path\To\remaining_time_widget.py C:\ProgramData\ScreenTimeWidget\remaining_time.txt
```
* The child can close the widget window with Alt+F4 if they want; this is just a visual reminder, the actual enforcement is done by monitor.py.


## Safety

Make sure to password-protect bios to prevent boot from other device.
Encrypt the hard-drive by bitlocker to prevent the child physically taking out the hard drive and modifying some system files from elsewhere. (This also calls for Windows Pro)

## Extra time request

If you want to grant extra time to the child, you generate a code that looks like this `<date>:<extra_time_seconds>:<signature>` where
* date is a nonce, normally today, that keeps otherwise-identical codes distinct
* extra time is an integer
* signature is 4 or more characters
A typical code can look like 2026-07-23:3600:a184 which would grant an extra hour (3600 seconds). Codes are not tied to a date -- the date is never checked against the calendar, so a code can be redeemed any day. Each code can only be redeemed once, tracked in `data/used_redeem_codes.json`; to issue a second code of the same amount on the same day, pass a different `--date`.

The child writes this code to the file specified in monitor.py text document.

To generate the codes, the parent can run the create_code.py script on his machine.
Both machines share a secret password (`data/secret.txt` on each machine, or the `CHILD_SECRET` env var on the parent's) which should not be shared with the child.


## Server accounts

An account is two halves that have to agree on the login name:

* a row in the `users` table, which says what family the parent belongs to -- `python server/add_user.py <login> <family>`
* a line in `/etc/nginx/htpasswd`, which says how the parent proves that login -- `sudo htpasswd /etc/nginx/htpasswd <login>`

Run `htpasswd` without `-c` to add a parent; the file holds one line per account and
already supports as many as you like. `-c` creates the file and silently truncates an
existing one, so it is only for the very first account.

nginx checks the password and passes the name it verified to the app as `X-Remote-User`;
`current_user` in `server/app.py` looks that name up to decide which family's devices the
page shows. The header is set from `$remote_user` inside the authenticated location and
blanked on `/api/` and `/health`, so a client cannot supply its own. The app must never be
reachable except through the proxy, so start uvicorn on `--host 127.0.0.1` (the default).

## Python dependencies

None!

## Use cases: what happens when...

Scenario by scenario, as the code behaves today. Times assume the default config (1 h daily limit, 5 h carryover cap, 60 s check interval).

### Daily limit and carryover

* **Child uses up the daily limit.** Shutdown is issued with a 300 s grace period, the monitor reports the final state to the server and exits. Known gap: each reboot afterwards buys roughly 6 uncharged minutes (60 s startup delay + 300 s grace) before the next shutdown, repeatable.
* **Child stops before the limit.** The unused remainder rolls over to the next day (if `CARRYOVER` is on), capped at 5 h total.
* **Machine stays off for a whole day.** Each fully skipped day banks one full daily limit, same 5 h cap. A day the machine was on, even briefly, banks only what was actually left.
* **Child is past the limit at midnight (e.g. after a negative grant).** The debt is forgiven: carryover is never negative, the new day starts with the full daily limit.
* **Child uses the machine outside allowed hours.** Shutdown with a 10 s grace, whatever time is remaining.

### Redeem codes

* **Child enters a valid code.** The time is added the same minute, once ever -- the code lands in `used_redeem_codes.json` and never works again, on any day.
* **Unused code time at midnight.** It is part of the day's remainder, so it carries over like any other unused time (same cap).

### Server grants

* **Parent grants time while the machine is on.** Applied within about a minute; the child sees a message.
* **Parent grants time while the machine is off.** The grant waits on the server indefinitely and is applied on whatever day the machine next syncs -- there is no expiry. A forgotten negative grant is therefore a delayed punishment for some future day.
* **Parent grants negative time.** It reduces today's remaining time; if that drops to zero or below, the machine shuts down on the next tick. The effect never outlives the day (see midnight forgiveness above), so a negative grant cannot ban more than the rest of today.
* **Parent grants -X, then corrects with +X before the -X was synced.** Both arrive in the same sync and cancel exactly. Pending (not yet synced) grants are visible on the parent page, so this case is recognizable there.
* **Parent grants -X, machine shuts down, parent corrects with +X the same day.** The final sync before shutdown acknowledged the -X; after a reboot the +X restores exactly what the -X took. Correct, at the cost of one reboot.
* **Parent grants -X, corrects with +X, but a midnight lies in between.** The -X evaporates at midnight (never carried), while the +X still applies in full -- the child ends up ahead by nearly the whole +X. To undo an already-applied punishment across days, grant back only what the child actually lost.
* **A grant arrives during the very last sync before shutdown.** It is applied and saved, but the shutdown already in progress is not cancelled; the time counts from the next boot.
* **Server is down or unreachable.** The local limit, codes and shutdowns all keep working; grants queue on the server and apply on the next successful sync. A grant is re-sent until the machine confirms it, so a grant can in rare crash timings be applied twice, but never lost.

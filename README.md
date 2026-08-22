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
2. Optionally edit `config.py` -- `DAILY_LIMIT_SECONDS` and the allowed-hours range, if the defaults don't suit you. Nothing there has to be changed to install: the installer lists the local accounts and asks which one is the child's, writing the answer to `data\target_user.txt` in the locked folder -- monitor.py refuses to start without that file, so upgrading by hand-copying the scripts is not enough, run the installer. It also generates a shared secret if you don't have one. The secret is deliberately **not** in `config.py`, which is tracked in git; it goes into the locked data folder. Whether typed or generated, the parent's machine needs the **same** secret for `create_code.py`, in its own `data/secret.txt` or in the `CHILD_SECRET` env var.
3. Right-click `install.ps1` -> **Run with PowerShell** (it re-launches itself as admin). It will:
   * install Python 3 machine-wide via winget if it isn't already present,
   * copy `monitor.py`, `remote_sync.py` + `config.py` into `C:\ProgramData\ScreenTime` and lock the folder so the child cannot read it (this is what protects `data\secret.txt`),
   * ask which local account is the child's, then for the shared secret (Enter generates one) and, optionally, the child token and URL for the parent's server, and write it all into the locked folder,
   * copy the overlay widget into `C:\ProgramData\ScreenTimeShared`, the one folder every local account may write in, and put an "Extra time" shortcut on the shared desktop pointing at the redeem file there,
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
* Edit `config.py`, which sits next to the scripts and holds every setting. Nothing has to be changed in monitor.py itself. The ones you will care about (the five the server can also change are entries of `DEFAULT_SETTINGS`, the rest are plain variables):
  * `DAILY_LIMIT_SECONDS` -- how many seconds per day is the maximal screentime
  * `CARRYOVER` -- if `True`, unused time (including unused extra time from redeemed codes) rolls over to the next day; if `False`, each day starts fresh at `DAILY_LIMIT_SECONDS` and a redeemed code only grants extra time for the day it's redeemed
  * `SHUTDOWN_DELAY_SECONDS` -- after system shut down, how many seconds is the grace period (to save things etc)
  * `EARLIEST_HOUR_INCLUDED` and `LATEST_HOUR_INCLUDED` -- range of hours the computer will be usable, for instance 6 and 20, to exclude night time
  * `SECRET_FILE` -- where the shared secret for signing extra-time codes is read from; the value must match the parent's machine
  * `SERVER_URL` -- the parent's server for remote grants, empty to run without one; the child token goes in `CHILD_TOKEN_FILE`
  * `REDEEM_FILE_PATH` -- the file the child writes a code into; it sits in `SHARED_DIR` and rarely needs changing
  * `DATA_DIR` -- where the per-day json files and the used-code list live

  Five of them can also be changed from the server; see below. The rest (poll intervals, the redeem signature length) rarely needs touching. It is ordinary python, so keep the quotes and the `r"..."` prefixes on the windows paths intact -- a syntax error there stops monitor.py from starting.


## Remaining time overlay

`remaining_time_widget.py` shows a small always-on-top "time left" box in the top-right corner of the child's screen. monitor.py publishes the seconds remaining today to `REMAINING_TIME_FILE_PATH` on every tick; the widget only reads that one file and is fully self-contained -- it never touches `config.py` or the locked monitor folder.

Setup, run under the **child's own account** (not SYSTEM):
* Nothing extra to grant — the file lives in `C:\ProgramData\ScreenTimeShared\` next to the widget script, and the installer grants every local account write access to that folder. The child can therefore overwrite the number or the widget script itself; both are cosmetic, since monitor.py rewrites the file every tick, the widget runs in the child's own session anyway, and enforcement never reads anything from there except the signed redeem code.
* The widget shows `Time: --` if the file stops being refreshed for more than `STALE_AFTER_SECONDS`, rather than leaving a dead value on screen. A stale `0` is kept as "Time's up", since monitor.py writes it and then exits to shut the machine down.
* Without arguments the widget reads `remaining_time.txt` from its own folder, which is where the installer puts both. Pass a path as the first argument to point it somewhere else. Colours, font and poll interval are at the top of the script.
* Put a shortcut to it in the child's Startup folder (`shell:startup`), targeting `pythonw.exe` (not `python.exe`, so no console window appears), e.g.
```
C:\Path\To\pythonw.exe C:\ProgramData\ScreenTimeShared\remaining_time_widget.py
```
* The child can hide the widget with **Ctrl+Alt+H** and bring it back with the same shortcut, whatever app has focus. The keyboard state is read directly instead of claiming the combination from Windows, so it can never clash with another program's shortcut -- the keys simply reach that program too. `HOTKEY_KEYS` at the top of the script picks the combination.
* Being on top costs nothing: clicks pass straight through the box to the window underneath (so it never blocks the close button of a maximised window), it never takes focus, and it stays out of Alt+Tab and the taskbar. That also means it cannot be closed with Alt+F4 any more -- hiding it is the shortcut above, and killing it for good is Task Manager. Either way this is just a visual reminder, the actual enforcement is done by monitor.py.


## Safety

Make sure to password-protect bios to prevent boot from other device.
Encrypt the hard-drive by bitlocker to prevent the child physically taking out the hard drive and modifying some system files from elsewhere. (This also calls for Windows Pro)

## Extra time request

If you want to grant extra time to the child, you generate a code that looks like this `<date>:<extra_time_seconds>:<signature>` where
* date is a nonce, normally today, that keeps otherwise-identical codes distinct
* extra time is an integer
* signature is 4 or more characters
A typical code can look like 2026-07-23:3600:a184 which would grant an extra hour (3600 seconds). Codes are not tied to a date -- the date is never checked against the calendar, so a code can be redeemed any day. Each code can only be redeemed once, tracked in `data/used_redeem_codes.json`; to issue a second code of the same amount on the same day, pass a different `--date`.

The child writes this code into `C:\ProgramData\ScreenTimeShared\extra_time.txt` (`REDEEM_FILE_PATH`), which the installer puts on the shared desktop as an "Extra time" shortcut -- the shared desktop shows up for every account, so it works whether or not the child's own Desktop has been moved into OneDrive. If the folder itself is ever deleted, monitor.py recreates it without the write permission, and redeeming stops working until install.ps1 is run again.

To generate the codes, the parent can run the create_code.py script on his machine. It imports nothing from the rest of the project, so copying that one file over is enough -- but its `SIGNATURE_CHARS` has to keep matching the one in the child's `config.py`, or every code is rejected.
Both machines share a secret password (`data/secret.txt` next to the script on each machine, or the `CHILD_SECRET` env var on the parent's) which should not be shared with the child.


## Settings from the server

The server can change the five settings in the `DEFAULT_SETTINGS` dict in `config.py`: `DAILY_LIMIT_SECONDS`, `CARRYOVER`, `MAX_CARRYOVER_SECONDS`, `EARLIEST_HOUR_INCLUDED` and `LATEST_HOUR_INCLUDED`. The `ALLOWED_VALUES` dict right below it states what each one may be set to. Nothing else can be reached that way: the values arrive over the network, so the paths that hold the signing secret, and `SERVER_URL` itself, stay under local control only.

They ride along in the answer to a sync, next to the grants, under a `config` key and with the names `config.py` uses:

```json
{"pending_grants": [{"id": 7, "seconds": 600}],
 "config": {"LATEST_HOUR_INCLUDED": 22, "CARRYOVER": false}}
```

An answer without that key -- which is every answer the server sends today -- changes nothing. The client is ready for it either way.

* Only the settings actually named are changed; the others keep what they had, so the server can send one without restating the rest.
* What arrives is stored in `data/override_config.json` and wins over `config.py`. That file is what puts the settings in force, so they survive reboots and keep applying while the server is unreachable. It belongs to the monitor -- change these settings from the server or in `config.py`, not by editing it; deleting the whole file is the one safe manual move, and goes back to the `config.py` values.
* A new value applies from the next tick, without restarting the monitor, and is written to the day's `event_log`.
* Values outside the range in `ALLOWED_VALUES`, and names not in it, are ignored rather than enforced.
* Hours that would leave no usable window at all are refused when they arrive, and the ones already in force stay: the machine would otherwise shut down every minute and never stay up long enough to receive a correction. So send **both** hours together when moving the window past the hours already set -- sending one at a time works only while each step leaves a usable window.

## Server accounts

An account is two halves that have to agree on the login name:

* a row in the `parents` table, which says what family the parent belongs to -- `python server/add_parent.py <login> <family>`
* a line in `/etc/nginx/htpasswd`, which says how the parent proves that login -- `sudo htpasswd -B -C 10 /etc/nginx/htpasswd <login>`

Run `htpasswd` without `-c` to add a parent; the file holds one line per account and
already supports as many as you like. `-c` creates the file and silently truncates an
existing one, so it is only for the very first account.

`-B` picks bcrypt, `-C 10` the work factor -- about 100 ms per check, so guessing costs
real CPU and a stolen file stays useless. Without them htpasswd writes MD5 (`$apr1$`),
which is worth cracking offline. nginx verifies the password on every request, so the
factor is a ceiling on how fast anyone can guess as well as on how fast a parent's page
loads; 10 is the balance, and much higher turns a flood of wrong passwords into real load.

nginx checks the password and passes the name it verified to the app as `X-Remote-User`;
`current_parent` in `server/app.py` looks that name up to decide which family's children the
page shows. The header is set from `$remote_user` inside the authenticated location and
blanked on `/api/` and `/health`, so a client cannot supply its own. The app must never be
reachable except through the proxy, so start uvicorn on `--host 127.0.0.1` (the default).

## Signing out

Basic auth has no sign-out, only a password the browser keeps re-sending, so the link in
the page header replaces it with a throwaway one. That only works if the throwaway is
*accepted* somewhere, which is what `/logout` is for:

```nginx
# htpasswd -bc /etc/nginx/htpasswd.logout logout logout
location = /logout {
    auth_basic "Restricted";                    # the same realm string as /
    auth_basic_user_file /etc/nginx/htpasswd.logout;
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header X-Remote-User $remote_user;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

It goes in the same `server` block as `location /`, and `= /logout` beats the prefix match,
so the throwaway file is consulted for that one path and the real htpasswd for everything
else. Without this block `/logout` falls into `location /`, the throwaway password is
rejected by the real htpasswd, and the browser is left prompting on a URL that still
carries it -- the exact loop the redirect exists to avoid, just parked one path further on.

The link points at `https://logout:logout@<host>/logout`, nginx accepts that pair against
the file above, the browser files it under the realm in place of the parent's real
password, and the app answers with a redirect to `/`, spelled out in full as
`https://<host>/`. That is where the 401 happens, on a URL with no credentials in it, so
the login box it opens can be answered normally. The full spelling is the point: a bare
`/` would be resolved against the URL the browser is on, and a resolved relative reference
inherits that URL's userinfo, quietly putting the bogus credentials back on the page that
must not have them.

Three things this depends on:

* **The realm string must be identical in both locations** -- `Restricted` as deployed,
  whatever `location /` says if that changes. Browsers cache passwords per origin *and*
  realm; under a different realm the throwaway would be filed alongside the real password
  rather than over it, and the parent would stay logged in.
* **The redirect has to come from the app, not from `return 302` in the location.**
  nginx runs `return` in the rewrite phase, before `auth_basic` in the access phase, so a
  redirect written there answers without ever checking the password -- and a password
  never checked is never cached, which is the whole point.
* **Never give a parent the login `logout`.** `add_parent.py` would let you, and that
  account's password would then be public knowledge.

The app refuses to serve `/logout` unless nginx hands it `X-Remote-User: logout`, so a
missing or unprotected location block fails with a visible 403 instead of a sign-out link
that quietly does nothing.

Firefox shows a "you are about to log in with the username logout" confirmation before
following the link; that is its anti-phishing warning about credentials in a URL, and
answering yes is correct here.

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

### Server settings

* **Parent changes the daily limit while the machine is on.** In force within about a minute, for today as well: if the new limit is below what the child already spent, the machine shuts down on the next tick. Time already banked as carryover for today is not recomputed.
* **Parent changes a setting while the machine is off.** It arrives on the next sync after the machine comes back, like a grant.
* **Server is down or unreachable.** The settings it sent last keep applying; the machine never reverts to `config.py` on its own.
* **Parent sends a value the client rejects.** It is dropped and the previous value stays, so the machine keeps running on settings that work rather than on the typo. The rest of the same answer still applies.

### Server grants

* **Parent grants time while the machine is on.** Applied within about a minute; the child sees a message.
* **Parent grants time while the machine is off.** The grant waits on the server indefinitely and is applied on whatever day the machine next syncs -- there is no expiry. A forgotten negative grant is therefore a delayed punishment for some future day.
* **Parent grants negative time.** It reduces today's remaining time; if that drops to zero or below, the machine shuts down on the next tick. The effect never outlives the day (see midnight forgiveness above), so a negative grant cannot ban more than the rest of today.
* **Parent grants -X, then corrects with +X before the -X was synced.** Both arrive in the same sync and cancel exactly. Pending (not yet synced) grants are visible on the parent page, so this case is recognizable there.
* **Parent grants -X, machine shuts down, parent corrects with +X the same day.** The final sync before shutdown acknowledged the -X; after a reboot the +X restores exactly what the -X took. Correct, at the cost of one reboot.
* **Parent grants -X, corrects with +X, but a midnight lies in between.** The -X evaporates at midnight (never carried), while the +X still applies in full -- the child ends up ahead by nearly the whole +X. To undo an already-applied punishment across days, grant back only what the child actually lost.
* **A grant arrives during the very last sync before shutdown.** It is applied and saved, but the shutdown already in progress is not cancelled; the time counts from the next boot.
* **Server is down or unreachable.** The local limit, codes and shutdowns all keep working; grants queue on the server and apply on the next successful sync. A grant is re-sent until the machine confirms it, so a grant can in rare crash timings be applied twice, but never lost.

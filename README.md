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
* Nothing extra to grant — `C:\Users\Public\` is readable by all local accounts by default, same as the redeem file already relies on.
* The widget takes the remaining-time file path as its first command-line argument (the installer fills it in from config.py's `REMAINING_TIME_FILE_PATH`); without an argument it falls back to the default at the top of the script. Colours, font and poll interval are in the same block.
* Put a shortcut to it in the child's Startup folder (`shell:startup`), targeting `pythonw.exe` (not `python.exe`, so no console window appears), e.g.
```
C:\Path\To\pythonw.exe C:\Path\To\remaining_time_widget.py C:\Users\Public\remaining_time.txt
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


## Python dependencies

None!

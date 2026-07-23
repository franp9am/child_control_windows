## About

A simple setup to limit childs screentime on a (typically windows) computer.

It sets up a daily screentime limit and supports allowing more time upon request.

Very basic. Compared to microsoft family safety, it has these advantages:

* Easier to set up
* Independent on cloud, all is fully local
* Works offline


## Setup

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
  * `SHUTDOWN_DELAY_SECONDS` -- after system shut down, how many seconds is the grace period (to save things etc)
  * `EARLIEST_HOUR_INCLUDED` and `LATEST_HOUR_INCLUDED` -- range of hours the computer will be usable, for instance 6 and 20, to exclude night time
  * `REDEEM_FILE_PATH` -- path to a local file the children can access, to write a code in case you grant him extra time
  * `DATA_DIR` -- where the per-day json files, the used-code list and `sec.txt` live

  The rest (poll intervals, the overlay's colours and font, the redeem signature length) rarely needs touching. It is ordinary python, so keep the quotes and the `r"..."` prefixes on the windows paths intact -- a syntax error there stops monitor.py from starting.


## Remaining time overlay

`remaining_time_widget.py` shows a small always-on-top "time left" box in the top-right corner of the child's screen. monitor.py publishes the seconds remaining today to `REMAINING_TIME_FILE_PATH` (defaults to `C:\Users\Public\eli_remaining_time.txt`, alongside the redeem file) on every tick; the widget only reads that one file, so it never needs access to `data/` or `sec.txt`.

Setup, run under the **child's own account** (not SYSTEM):
* Nothing extra to grant — `C:\Users\Public\` is readable by all local accounts by default, same as the redeem file already relies on.
* Copy `config.py` next to `remaining_time_widget.py`, it reads its settings from there too. The copy holds only paths and colours, no secret, but its `REMAINING_TIME_FILE_PATH` must match the one monitor.py uses.
* Colours, font and poll interval of the overlay are the last block of config.py.
* Put a shortcut to it in the child's Startup folder (`shell:startup`), targeting `pythonw.exe` (not `python.exe`, so no console window appears), e.g.
```
C:\Path\To\pythonw.exe C:\Path\To\remaining_time_widget.py
```
* The child can close the widget window with Alt+F4 if they want; this is just a visual reminder, the actual enforcement is done by monitor.py.


## Safety

Make sure to password-protect bios to prevent boot from other device.
Encrypt the hard-drive by bitlocker to prevent the child physically taking out the hard drive and modifying some system files from elsewhere. (This also calls for Windows Pro)

## Extra time request

If you want to grant extra time to the child, you generate a code that looks like this `<extra_time_seconds>:<signature>` where
* extra time is an integer
* signature is 4 or more characters
A typical code can look like 3600:a184 which would grant an extra hour (3600 seconds). Codes are not tied to a date; each code can only be redeemed once, tracked in `data/used_redeem_codes.json`.

The child writes this code to the file specified in monitor.py text document.

To generate the codes, the parent can run the create_code.py script on his machine.
Both machines share a secret password which should not be shared with the child.


## Python dependencies

None!

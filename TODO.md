# TODO

Ordered by importance within each section.

## Client / monitor

* Auto-update. The task runs a launcher: check for updates, then start the
  monitor. It fetches the manifest from `releases/latest/download/` on GitHub;
  if newer than the installed version, it verifies the Ed25519 signature
  (public key baked in, private key off GitHub and CI, verify vendored in pure
  Python), downloads the zip, checks every hash, only then replaces the files,
  its own included, and writes the version marker last so a half-applied
  update repeats. Any failure is logged and the monitor starts anyway. Never
  downgrades; rollback is a new tag. The server plays no part. `UPDATE_MODE`
  in a file next to the launcher; the installer sets `manual` when the machine
  does not sync. From then on nobody is present when new code first runs, so
  every change to the files on disk ships with its migration in the monitor's
  start, deleted once the dashboard shows no machine before it; the updater
  only copies files.
* Run the monitor as a Windows service instead of a scheduled task, still in
  Python: a `service.py` of about 80 lines does the Service Control Manager
  handshake through `ctypes` (dispatcher, control handler, RUNNING reported at
  once, the loop in a thread waiting on a stop event); the monitor's code does
  not change. The installer runs `sc create` on the private python.exe as
  LocalSystem plus `sc failure` for automatic restart, and removes the old
  task; the uninstaller stops and deletes the service. The widget stays a task,
  it needs the child's session. Why: on 2026-09-15 the Scheduler launched no
  SYSTEM or boot-triggered task for hours while the test VM sat at a critical
  battery, so the monitor never started; a service does not depend on Task
  Scheduler at all, SCM restarts it after a crash, and the child cannot end it
  from Task Manager. Half a day of code, a day of testing on a real machine;
  the SCM handshake has no unit test.
* The parent's page warns when a machine has not reported for a day. A monitor
  that never starts looks like a quiet day otherwise.
* Per-weekday override for the allowed hours, like `DAILY_LIMIT_OVERRIDES` does
  for the limit, e.g. later on Friday and Saturday.
* Send recent `event_log` lines (or at least the last caught exception) with each
  sync, so debugging works from the server page without machine access.
* Time zone is changeable by a standard user, which rolls `datetime.now()` into
  a new date and a fresh daily limit.
* The same atomic write (temp file + `os.replace`) is copied all over; it wants
  one shared home.
* Split `config.py` into config and settings. Config is what is fixed at install:
  paths, intervals, the version, the update mode. Settings are what the parent
  changes from the server: schema, validation, the file, `get_config` renamed to
  say what it returns. The installer's file list in `install.ps1` must name the
  new module.
* Several children on one machine. The layout is ready since 0.5: a child is a
  directory under `data/` and under the shared dir, and the monitor loops over
  them. Left: the redeem code as `<child>:<date>:<seconds>:<sign>` with the
  child signed too, so a code redeems for one child only; the installer adding
  a child without disturbing the ones there (one widget task per child, the
  monitor task kept); one more `icacls` locking each child's shared folder to
  that account, so siblings cannot see or edit each other's files. The
  installer's move of a pre-0.5 layout goes once no such machine remains.

## Server-side

* Test the server against the report of each released monitor version, since
  it has to stay compatible with every one still installed (see the README).
* `settings_in_words` hardcodes the five setting names, while the rest of the
  settings path takes names and types from whatever the child reports. A
  renamed, missing or malformed setting is a 500 on both `/` and `/settings` for
  that child. Render the compact line only when the known names fit, else fall
  back to plain `name=value`.
* Settings UI: a widget per setting, keyed by name (durations, hour picker,
  weekday sliders over `DAILY_LIMIT_OVERRIDES`); unknown names fall back to the
  JSON box. The client stays the validator. A name's meaning never changes,
  new meaning means new name; a server test checks every widget name exists
  in the client's `SETTINGS`.
* Real login: replace BasicAuth with a session cookie and a login form.
* Server logging.
* One-step release. Today it is three edits: `MONITOR_VERSION` in `config.py`,
  `$Ref` in `bootstrap.ps1`, then the tag. Let the tag be the only source:
  `bootstrap.ps1` asks the GitHub API for the latest release instead of carrying
  a pin, and the monitor reads its version from a file written at release time.
  The same release step writes the manifest of file hashes and signs it, for
  auto-update.
* Simplify installation: family, parent and child creation in the DB and the
  corresponding logins, with less effort from the maintainer.

## Product, once mature

* A general description of what this is, in Czech and English, for the site
  and the top of the README.
* A parent's manual: creating an account, adding children, installing on the
  child's machine. The README covers the install for now.

## Someday / maybe

* Full client rewrite in C# with an exe installer.

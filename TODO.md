# TODO

Ordered by importance within each section.

## Client / monitor (each change needs a visit to the child's machine, until auto-update ships)

* Tests, before more client changes: done. The pure logic, the sync, the
  settings file, the main loop as scenarios in `test_main_loop.py` and the
  widget's pure helpers. Untested on purpose: `os_tooling` (needs real
  sessions), `main()` and the widget's Tk part.
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
* Warn five minutes before night: one `os_tooling.notify` from `tick` when
  `is_night_time(now + timedelta(minutes=5), settings)`, with a flag in the
  data file so it fires once a day. Reusing `is_night_time` keeps it right
  when night never comes (`LATEST_HOUR_INCLUDED = 23`) and across midnight.
  The time running out needs no warning, the widget turns red below five
  minutes. Leave the widget's number alone: showing "seconds to night" there
  would make two hours jump to five minutes.
* Per-weekday override for the allowed hours, like `DAILY_LIMIT_OVERRIDES` does
  for the limit, e.g. later on Friday and Saturday.
* Enablers for several children on one machine, the full thing later: paths,
  secret and token derived from the child name through one function, files
  under `data/<child>/` and per-child files in the shared dir, the redeem code
  as `<child>:<date>:<seconds>:<sign>` with the child signed too, the loop
  written as "for each child" while there is one. Nothing is machine-wide:
  the monitor moves the whole old data folder under the child on start.
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
* Several children on one machine, on the enablers above.

## Server-side, anytime later (no access to the child's machine needed)

* Stay compatible with every monitor version still installed. Until auto-update
  ships, a client is only updated by a visit; afterwards the window shrinks to
  the rollout plus the machines on manual mode, but it never closes. The server
  must accept an old report and send back only what that version understands.
  Test the server against the report of each released version.
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

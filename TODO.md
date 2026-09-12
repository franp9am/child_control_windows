# TODO

Ordered by importance within each section.

## Client / monitor (each change needs a visit to the child's machine)

* Tests, before more client changes. Done for the pure logic.
* Send recent `event_log` lines (or at least the last caught exception) with each
  sync, so debugging works from the server page without machine access.
* Time zone is changeable by a standard user, which rolls `datetime.now()` into
  a new date and a fresh daily limit.
* The same atomic write (temp file + `os.replace`) is copied all over; it wants
  one shared home.
* Split `config.py` into config and settings. Config is what is fixed at install:
  paths, intervals, the version. Settings are what the parent changes from the
  server: schema, validation, the file, `get_config` renamed to say what it
  returns. The installer's file list in `install.ps1` must name the new module.
* Support more accounts / children on one machine.

## Server-side, anytime later (no access to the child's machine needed)

* Stay compatible with every monitor version still installed: a client is only
  updated by a visit, so the server must accept an old report and send back
  only what that version understands. Test the server against the report of
  each released version.
* `settings_in_words` hardcodes the five setting names, while the rest of the
  settings path takes names and types from whatever the child reports. A
  renamed, missing or malformed setting is a 500 on both `/` and `/settings` for
  that child. Render the compact line only when the known names fit, else fall
  back to plain `name=value`.
* Real login: replace BasicAuth with a session cookie and a login form.
* Server logging.
* One-step release. Today it is three edits: `MONITOR_VERSION` in `config.py`,
  `$Ref` in `bootstrap.ps1`, then the tag. Let the tag be the only source:
  `bootstrap.ps1` asks the GitHub API for the latest release instead of carrying
  a pin, and the monitor reads its version from a file written at release time.
* Simplify installation: family, parent and child creation in the DB and the
  corresponding logins, with less effort from the maintainer.

## Someday / maybe

* Auto-update, if we decide so: a launcher that fetches a newer monitor from the
  server, verifies it and runs it. It would spare the visits to the machine, but
  it is code running as SYSTEM that replaces itself with whatever a server
  offers, which sits badly with a project that wants to be simple, stable and
  readable in full by the parent. Signing narrows the risk, not the shape.
  Meanwhile `bootstrap.ps1` is the manual path: one command, run at the machine,
  on purpose.
* Full client rewrite in C# with an exe installer.

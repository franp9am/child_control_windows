# TODO

Ordered by importance within each section.

## Client / monitor (needs the child's machine, until auto-update exists)

* Auto-update: a launcher that fetches a newer monitor from the server, verifies
  it, and then runs it. Everything below becomes deliverable without touching the
  machine again. The code it fetches runs as SYSTEM, so a release must carry a
  signature and an unverified one is ignored. 
* Tests, before more client changes. Start with the pure logic:
  `compute_carryover_sec`, `seconds_to_charge`, `handle_redeem_file`,
  `config.validated_settings`.
* Send recent `event_log` lines (or at least the last caught exception) with each
  sync, so debugging works from the server page without machine access.
* Time zone is changeable by a standard user, which rolls `datetime.now()` into
  a new date and a fresh daily limit.
* Per-weekday daily limit: one extra setting holding a dict, e.g.
  `DAILY_LIMIT_OVERRIDES: {"mon": 1800}`. The server is nearly free: the form is
  JSON text already and the type check compares dict with dict. Client
  decisions: the `allowed` spec in `SETTINGS` cannot express a dict, so each
  setting needs a validator function; `compute_carryover_sec` credits each
  skipped day its own limit; `remaining_seconds` must use the limit in force on
  the file's date, not today's (harmless now, wrong once Sunday's leftover is
  computed with Monday's limit); key format, day names or ISO numbers. Limit
  only, the hours window stays global.
* `MAX_CARRYOVER_SECONDS: null` means no cap. Nullability is a per-setting flag
  in `SETTINGS` (only this one), the default stays a number so a fresh report
  still types the field, the `min()` in `compute_carryover_sec` gets a branch,
  `settings_in_words` gets a third case "carryover unlimited". Server type check
  is exempt when either side is null. Keep the `CARRYOVER` bool: off, capped
  and unlimited over two plain fields beats a sentinel.
* The same atomic write (temp file + `os.replace`) is copied all over; it wants
  one shared home.
* Support more accounts / children on one machine.

## Server-side, anytime later (no access to the child's machine needed)

* `settings_in_words` hardcodes the five setting names, while the rest of the
  settings path takes names and types from whatever the child reports. A
  renamed, missing or malformed setting is a 500 on both `/` and `/settings` for
  that child. Render the compact line only when the known names fit, else fall
  back to plain `name=value`.
* Real login: replace BasicAuth with a session cookie and a login form.
* Server logging.
* Simplify installation: family, parent and child creation in the DB and the
  corresponding logins, with less effort from the maintainer.

## Someday / maybe

* Full client rewrite in C# with an exe installer. If this is real, the
  launcher above is throwaway work; decide before starting it.

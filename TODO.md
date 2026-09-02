# TODO

## Before the client freezes

* Send recent `event_log` lines (or at least the last caught exception) with each
  sync, so debugging works from the server page without machine access.
* Time zone is changeable by a standard user, which rolls `datetime.now()` into a new date and a fresh daily limit.
* The same atomic write (temp file + `os.replace`) is copied all over; it wants one
  shared home.
* `send_message` and `user_logged_in` could move to `os_tooling.py`, if the user is passed in.
* No tests. Start with the pure logic: `compute_carryover_sec`, `seconds_to_charge`,
  `handle_redeem_file`, `config.validated_settings`. Client bugs are expensive after the freeze.

## Server-side, anytime later (no access to the child's machine needed)

* `settings_in_words` hardcodes the five setting names, while the rest of the settings
  path takes names and types from whatever the child reports. A renamed, missing or
  malformed setting is a 500 on both `/` and `/settings` for that child. Render the
  compact line only when the known names fit, else fall back to plain `name=value`.
* Real login on the server: Replace BasicAuth with a session cookie and a login form.
* Server logging.
* Simplify installation + family, parent, child creation in DB and corresponsing login: less effort of the maintainer ?

## Someday / maybe

* Support more accounts / children on one machine
* ? long term -- full client rewrite to C# + exe installer ?

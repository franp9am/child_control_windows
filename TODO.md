# TODO

## Before the client freezes

Ordered by leverage; if only two get done, the first two.

* Send `monitor_version` on every sync, now, as a hardcoded constant -- optional
  field, like `rejected_settings`. Display and diagnostics on the parent page
  only, never protocol branching. Can't be retrofitted remotely.
* Wire `os_tooling.py` into monitor.py, replacing `query user` and `msg`. The module
  is written but nothing imports it, so the subprocess path is still the live one --
  and neither tool exists on windows Home: notifications fail silently and every tick
  falls back to a loose `tasklist | findstr` substring match. Note `users_at_screen()`
  also stops charging a locked screen, which changes the night-time branch: a locked
  machine would no longer be shut down. Decide that, then test on Home.
* Send recent `event_log` lines (or at least the last caught exception) with each
  sync, so debugging works from the server page without machine access.
* `icacls` exit code unchecked on the Python dir (install.ps1:112), the bug already fixed
  for $MonitorDir. If it fails the child can plant sitecustomize.py that runs as SYSTEM.
* Time zone is changeable by a standard user, which rolls `datetime.now()` into a new date and a fresh daily limit.
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

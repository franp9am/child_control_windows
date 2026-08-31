# TODO

## Before the client freezes (deployment to J.'s machine; client changes cost a visit after that)

Ordered by leverage; if only two get done, the first two.

* Send `monitor_version` on every sync, now, as a hardcoded constant -- optional
  field, like `rejected_settings`. Display and diagnostics on the parent page
  only, never protocol branching. Can't be retrofitted remotely.
* Send recent `event_log` lines (or at least the last caught exception) with each
  sync, so debugging works from the server page without machine access.
* `icacls` exit code unchecked on the Python dir (install.ps1:112), the bug already fixed
  for $MonitorDir. If it fails the child can plant sitecustomize.py that runs as SYSTEM.
* Time zone is changeable by a standard user, which rolls `datetime.now()` into a new date and a fresh daily limit.
* No tests. Start with the pure logic: `compute_carryover_sec`, `seconds_to_charge`,
  `handle_redeem_file`, `config.validated_settings`. Client bugs are expensive after the freeze.

## Server-side, anytime later (no access to the child's machine needed)

* Real login on the server: Replace BasicAuth with a session cookie and a login form.
* Server logging.
* Simplify installation + family, parent, child creation in DB and corresponsing login: less effort of the maintainer ?

## Someday / maybe

* Replace `query user` and `msg` by native windows functions from ctypes
* Support more accounts / children on one machine
* ? long term -- full client rewrite to C# + exe installer ?

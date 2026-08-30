# TODO

* Add settings control on the server
* Real login on the server: Replace BasicAuth with a session cookie and a login form.
* Replace `query user` and `msg` by native windows functions from ctypes
* Support more accounts / children on one machine
* Simplify installation + family, parent, child creation in DB and corresponsing login: less effort of the maintainer ?
* ? long term -- full client rewrite to C# + exe installer ?
* No tests. Start with the pure logic: `compute_carryover_sec`, `seconds_to_charge`,
  `handle_redeem_file`, `config.validated_settings`. Do this before the rewrites above.
* Time zone is changeable by a standard user, which rolls `datetime.now()` into a new date and a fresh daily limit.
* `icacls` exit code unchecked on the Python dir (install.ps1:112), the bug already fixed
  for $MonitorDir. If it fails the child can plant sitecustomize.py that runs as SYSTEM.

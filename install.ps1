$ErrorActionPreference = "Stop"
$MonitorDir = "C:\ProgramData\ScreenTime"        # monitor + data; hidden from the child
$WidgetDir  = "C:\ProgramData\ScreenTimeWidget"  # overlay; the child may read this

# Re-launch as administrator if we aren't already.
$admin = [Security.Principal.WindowsBuiltInRole]::Administrator
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole($admin)) {
    Start-Process powershell "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    return
}
$src = $PSScriptRoot

# The child's account name lives in config.py -- read it from there.
$configText = Get-Content -Raw "$src\config.py"
$childUser = [regex]::Match($configText, 'TARGET_USER\s*=\s*["'']([^"'']+)').Groups[1].Value
if (-not $childUser) { throw "Set TARGET_USER in config.py first." }

# The shared secret also lives in config.py (protected later by the folder
# ACL). Refuse to install while it is unset or too weak: at least 8 bytes,
# i.e. 16 hex characters.
$secretHex = [regex]::Match($configText, 'SECRET_HEX\s*=\s*["'']([^"'']*)').Groups[1].Value
if ($secretHex -notmatch '^[0-9a-fA-F]{16,}$' -or $secretHex.Length % 2 -ne 0) {
    throw "Set SECRET_HEX in config.py to the shared secret first: at least 8 bytes = 16 hex chars (generate with: python -c `"import secrets; print(secrets.token_hex(16))`")."
}

# The widget task needs the remaining-time file path as an argument.
$remainingFile = [regex]::Match($configText, 'REMAINING_TIME_FILE_PATH\s*=\s*Path\(r?["'']([^"'']+)').Groups[1].Value
if (-not $remainingFile) { throw "Could not read REMAINING_TIME_FILE_PATH from config.py." }

# Install Python machine-wide if it's missing (the widget needs its bundled tkinter).
# Must be a machine-wide install under Program Files, not whatever python.exe
# happens to resolve off the invoking (admin) user's PATH -- a per-user install
# living under that user's own profile is inaccessible to the child's account,
# which makes the widget task fail with Access Denied when it tries to launch it.
$targetDir = "C:\Python311"   # no spaces -- avoids quoting the override string has to survive PowerShell -> winget -> installer
$python = (Get-ChildItem "C:\Program Files\Python3*\python.exe", "$targetDir\python.exe" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
if (-not $python) {
    # --scope machine alone isn't enough: if a per-user install of the same
    # version already exists (e.g. under the admin's own profile), winget/the
    # Python installer tries to convert it in place instead of installing
    # fresh under Program Files. Force an explicit target dir to avoid that.
    $override = "/quiet InstallAllUsers=1 PrependPath=0 TargetDir=$targetDir"
    winget install --id Python.Python.3.11 -e --scope machine --accept-package-agreements --accept-source-agreements --override $override
    $python = (Get-ChildItem "$targetDir\python.exe" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
}
if (-not $python) { throw "Could not find or install a machine-wide Python under C:\Program Files." }
$pythonw = Join-Path (Split-Path $python) pythonw.exe   # windowless twin, for the widget

# Monitor folder: copy the files, then lock it to SYSTEM + Administrators only.
# That lock is what stops the child reading the secret in config.py and
# forging codes.
New-Item -ItemType Directory -Force "$MonitorDir\data" | Out-Null
Copy-Item "$src\monitor.py", "$src\config.py" $MonitorDir -Force
icacls $MonitorDir /inheritance:r /grant "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" | Out-Null

# Widget folder: child-readable, holds only the overlay script. (Remove the
# config.py copy older installs put here -- the widget no longer reads it.)
New-Item -ItemType Directory -Force $WidgetDir | Out-Null
Copy-Item "$src\remaining_time_widget.py" $WidgetDir -Force
Remove-Item "$WidgetDir\config.py" -Force -ErrorAction SilentlyContinue

# Task 1 -- run monitor.py as SYSTEM at every startup.
$run  = New-ScheduledTaskAction -Execute $python -Argument "`"$MonitorDir\monitor.py`"" -WorkingDirectory $MonitorDir
$who  = New-ScheduledTaskPrincipal -UserId SYSTEM -LogonType ServiceAccount -RunLevel Highest
$opts = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask "ScreenTimeMonitor" -Action $run -Trigger (New-ScheduledTaskTrigger -AtStartup) -Principal $who -Settings $opts -Force | Out-Null

# Task 2 -- show the overlay in the child's session when they log in.
$run = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$WidgetDir\remaining_time_widget.py`" `"$remainingFile`"" -WorkingDirectory $WidgetDir
$who = New-ScheduledTaskPrincipal -UserId $childUser -LogonType Interactive
Register-ScheduledTask "ScreenTimeWidget" -Action $run -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $childUser) -Principal $who -Force | Out-Null

Write-Host "`nDone. Monitor starts after a reboot; the widget appears when $childUser logs in."

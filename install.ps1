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
$childUser = [regex]::Match((Get-Content -Raw "$src\config.py"), 'TARGET_USER\s*=\s*["'']([^"'']+)').Groups[1].Value
if (-not $childUser) { throw "Set TARGET_USER in config.py first." }

# Install Python machine-wide if it's missing (the widget needs its bundled tkinter).
$python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $python) {
    winget install --id Python.Python.3.11 -e --scope machine --accept-package-agreements --accept-source-agreements
    $python = (Get-ChildItem "C:\Program Files\Python3*\python.exe" | Select-Object -First 1).FullName
}
$pythonw = Join-Path (Split-Path $python) pythonw.exe   # windowless twin, for the widget

# Monitor folder: copy the files, then lock it to SYSTEM + Administrators only.
# That lock is what stops the child reading data\sec.txt and forging codes.
New-Item -ItemType Directory -Force "$MonitorDir\data" | Out-Null
Copy-Item "$src\monitor.py", "$src\config.py" $MonitorDir -Force
icacls $MonitorDir /inheritance:r /grant "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" | Out-Null

# Shared secret -> data\sec.txt (must match create_code.py on the parent's machine).
$secret = (Read-Host "Shared secret in hex (leave blank to keep the existing one)").Trim()
if ($secret) { Set-Content "$MonitorDir\data\sec.txt" $secret.ToLower() -NoNewline -Encoding ASCII }

# Widget folder: child-readable, holds only the overlay and a copy of config.py.
New-Item -ItemType Directory -Force $WidgetDir | Out-Null
Copy-Item "$src\remaining_time_widget.py", "$src\config.py" $WidgetDir -Force

# Task 1 -- run monitor.py as SYSTEM at every startup.
$run  = New-ScheduledTaskAction -Execute $python -Argument "`"$MonitorDir\monitor.py`"" -WorkingDirectory $MonitorDir
$who  = New-ScheduledTaskPrincipal -UserId SYSTEM -LogonType ServiceAccount -RunLevel Highest
$opts = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask "ScreenTimeMonitor" -Action $run -Trigger (New-ScheduledTaskTrigger -AtStartup) -Principal $who -Settings $opts -Force | Out-Null

# Task 2 -- show the overlay in the child's session when they log in.
$run = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$WidgetDir\remaining_time_widget.py`"" -WorkingDirectory $WidgetDir
$who = New-ScheduledTaskPrincipal -UserId $childUser -LogonType Interactive
Register-ScheduledTask "ScreenTimeWidget" -Action $run -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $childUser) -Principal $who -Force | Out-Null

Write-Host "`nDone. Monitor starts after a reboot; the widget appears when $childUser logs in."

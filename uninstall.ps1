<#
    uninstall.ps1 -- removes what install.ps1 set up.

    Right-click -> "Run with PowerShell" (it self-elevates). It unregisters the
    two scheduled tasks, deletes the install folders and removes the desktop
    shortcut. Pass -KeepData to leave the data\ folder (used codes, per-day
    json) in place.
#>
[CmdletBinding()]
param(
    [string]$MonitorDir = "C:\ProgramData\ScreenTime",
    [string]$SharedDir  = "C:\ProgramData\ScreenTimeShared",
    [string]$MonitorTaskName = "ScreenTimeMonitor",
    [string]$WidgetTaskName  = "ScreenTimeWidget",
    [switch]$KeepData
)

$ErrorActionPreference = "Stop"

$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Re-launching with administrator rights..." -ForegroundColor Yellow
    $argList = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"")
    if ($KeepData) { $argList += "-KeepData" }
    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList $argList
    return
}

foreach ($t in @($MonitorTaskName, $WidgetTaskName)) {
    if (Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $t -Confirm:$false
        Write-Host "Removed scheduled task '$t'" -ForegroundColor Green
    }
}

# Stopping the task doesn't always kill an already-running instance launched by
# a previous boot, so also kill any monitor.py/widget process directly by
# command line before deleting their folders.
Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
    Where-Object {
        $_.CommandLine -match [regex]::Escape($MonitorDir) -or
        $_.CommandLine -match [regex]::Escape($SharedDir)
    } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped running process (PID $($_.ProcessId))" -ForegroundColor Green
    }

if (Test-Path $SharedDir) {
    Remove-Item -LiteralPath $SharedDir -Recurse -Force
    Write-Host "Deleted $SharedDir" -ForegroundColor Green
}

$link = "$env:PUBLIC\Desktop\Extra time.lnk"
if (Test-Path $link) {
    Remove-Item -LiteralPath $link -Force
    Write-Host "Deleted $link" -ForegroundColor Green
}

if (Test-Path $MonitorDir) {
    if ($KeepData) {
        Get-ChildItem -LiteralPath $MonitorDir -Exclude "data" | Remove-Item -Recurse -Force
        Write-Host "Deleted $MonitorDir contents but kept data\ (--KeepData)" -ForegroundColor Green
    } else {
        Remove-Item -LiteralPath $MonitorDir -Recurse -Force
        Write-Host "Deleted $MonitorDir" -ForegroundColor Green
    }
}

Write-Host "`nDone. Reboot to be sure the monitor is no longer running." -ForegroundColor Green

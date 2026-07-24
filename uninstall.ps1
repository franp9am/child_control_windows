<#
    uninstall.ps1 -- removes what install.ps1 set up.

    Right-click -> "Run with PowerShell" (it self-elevates). It unregisters the
    two scheduled tasks and deletes the install folders. Pass -KeepData to leave
    the data\ folder (used codes, per-day json, sec.txt) in place.
#>
[CmdletBinding()]
param(
    [string]$MonitorDir = "C:\ProgramData\ScreenTime",
    [string]$WidgetDir  = "C:\ProgramData\ScreenTimeWidget",
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
        Unregister-ScheduledTask -TaskName $t -Confirm:$false
        Write-Host "Removed scheduled task '$t'" -ForegroundColor Green
    }
}

if (Test-Path $WidgetDir) {
    Remove-Item -LiteralPath $WidgetDir -Recurse -Force
    Write-Host "Deleted $WidgetDir" -ForegroundColor Green
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

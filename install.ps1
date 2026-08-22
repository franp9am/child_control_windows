$ErrorActionPreference = "Stop"
$MonitorDir    = "C:\ProgramData\ScreenTime"        # monitor + data; hidden from the child
$OldWidgetDir  = "C:\ProgramData\ScreenTimeWidget"  # older installs; removed further down

# Re-launch as administrator if we aren't already.
$admin = [Security.Principal.WindowsBuiltInRole]::Administrator
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole($admin)) {
    Start-Process powershell "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    return
}
$src = $PSScriptRoot

$configText = Get-Content -Raw "$src\config.py"

# Which account is the child's. A typed name invites a typo that would leave the
# monitor watching an account nobody uses, so offer the real ones and check.
$enabledUsers = @(Get-LocalUser | Where-Object { $_.Enabled } | ForEach-Object { $_.Name })
$adminUsers = @()
try {
    $adminUsers = @(Get-LocalGroupMember -SID "S-1-5-32-544" | ForEach-Object { ($_.Name -split '\\')[-1] })
} catch { }   # an orphaned SID in the group makes this throw; then nothing is filtered out
$candidates = @($enabledUsers | Where-Object {
    $_ -notin $adminUsers -and $_ -notin @("Guest", "DefaultAccount", "WDAGUtilityAccount")
})

if ($candidates.Count -eq 1) { $defaultUser = $candidates[0] } else { $defaultUser = "" }

Write-Host "Local accounts: $($enabledUsers -join ', ')"
$userPrompt = "Which one is the child's account"
if ($defaultUser) { $userPrompt += " (Enter for $defaultUser)" }
$childUser = (Read-Host $userPrompt).Trim()
if (-not $childUser) { $childUser = $defaultUser }
if ($enabledUsers -notcontains $childUser) {
    throw "'$childUser' is not an enabled local account. Pick one of: $($enabledUsers -join ', ')"
}

# The folder the child may write in -- config.py is the single source for it.
$SharedDir = [regex]::Match($configText, 'SHARED_DIR\s*=\s*Path\(r?["'']([^"'']+)').Groups[1].Value
if (-not $SharedDir) { throw "Could not read SHARED_DIR from config.py." }
$redeemFile = Join-Path $SharedDir "extra_time.txt"   # must match REDEEM_FILE_PATH in config.py

# Both credentials live in files inside the locked data folder, never in
# config.py, which is tracked in git. Ask for them before anything is installed;
# they are written further down, once the folder ACL is in place.
$secretFile = "$MonitorDir\data\secret.txt"
$tokenFile  = "$MonitorDir\data\device_token.txt"
$userFile   = "$MonitorDir\data\target_user.txt"

$secretPrompt = "Shared secret for signing extra-time codes, at least 16 hex characters"
if (Test-Path $secretFile) { $secretPrompt += " (Enter keeps the current one)" }
else                       { $secretPrompt += " (Enter to generate one)" }
$secretHex = (Read-Host $secretPrompt).Trim()
$generatedSecret = ""
if ($secretHex) {
    if ($secretHex -notmatch '^[0-9a-fA-F]{16,}$' -or $secretHex.Length % 2 -ne 0) {
        throw "The secret must be an even number of hex characters, at least 16."
    }
} elseif (-not (Test-Path $secretFile)) {
    $bytes = New-Object byte[] 16
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $secretHex = -join ($bytes | ForEach-Object { $_.ToString("x2") })
    $generatedSecret = $secretHex   # printed at the end, for the parent's machine
}

$tokenPrompt = "Device token from add_device.py on the parent's server"
if (Test-Path $tokenFile) {
    $tokenPrompt += " (Enter keeps the current one)"
} else {
    $tokenPrompt += " (Enter to run without server syncing)"
}
$deviceToken = (Read-Host $tokenPrompt).Trim()

# Not written to a file like the secret and token: SERVER_URL is a plain
# variable in config.py, so it's patched into the copy under $MonitorDir
# below, straight after that file is copied there. Never into $src\config.py,
# which is tracked in git -- a real hostname doesn't belong in the repo.
$existingServerUrl = ""
if (Test-Path "$MonitorDir\config.py") {
    $existingServerUrl = [regex]::Match([IO.File]::ReadAllText("$MonitorDir\config.py"), 'SERVER_URL\s*=\s*"([^"]*)"').Groups[1].Value
}
$serverUrlPrompt = "Parent's server URL, e.g. https://screentime.example.com"
if ($existingServerUrl) { $serverUrlPrompt += " (Enter keeps $existingServerUrl)" }
else                    { $serverUrlPrompt += " (Enter to run without server syncing)" }
$serverUrl = (Read-Host $serverUrlPrompt).Trim()
if (-not $serverUrl) { $serverUrl = $existingServerUrl }

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
# That lock is what stops the child reading data\secret.txt and forging codes.
New-Item -ItemType Directory -Force "$MonitorDir\data" | Out-Null
Copy-Item "$src\monitor.py", "$src\remote_sync.py", "$src\config.py" $MonitorDir -Force
$copiedConfigPath = "$MonitorDir\config.py"
[IO.File]::WriteAllText($copiedConfigPath, [IO.File]::ReadAllText($copiedConfigPath).Replace('SERVER_URL = ""', "SERVER_URL = `"$serverUrl`""))
icacls $MonitorDir /inheritance:r /grant "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" | Out-Null

# Written only now, so neither credential ever sits in a folder the child can read.
if ($secretHex)   { Set-Content -Path $secretFile -Value $secretHex   -Encoding ascii -NoNewline }
if ($deviceToken) { Set-Content -Path $tokenFile  -Value $deviceToken -Encoding ascii -NoNewline }
# UTF-8 without a BOM, unlike the two above: an account name is not always ascii.
[IO.File]::WriteAllText($userFile, $childUser)

# Shared folder: every local account may write here. It holds only the overlay
# script, the number it shows and the redeem file -- nothing that has to be
# trusted, since the codes inside are signed and checked by monitor.py.
New-Item -ItemType Directory -Force $SharedDir | Out-Null
icacls $SharedDir /grant "*S-1-5-32-545:(OI)(CI)M" | Out-Null   # *S-1-5-32-545 = BUILTIN\Users
Copy-Item "$src\remaining_time_widget.py" $SharedDir -Force
if (-not (Test-Path $redeemFile)) { New-Item -ItemType File $redeemFile | Out-Null }
if (Test-Path $OldWidgetDir) { Remove-Item $OldWidgetDir -Recurse -Force -ErrorAction SilentlyContinue }

# The shortcut goes on the shared desktop, which every account sees -- the
# child's own Desktop folder may have been moved into OneDrive.
$link = (New-Object -ComObject WScript.Shell).CreateShortcut("$env:PUBLIC\Desktop\Extra time.lnk")
$link.TargetPath = $redeemFile
$link.Save()

# Task 1 -- run monitor.py as SYSTEM at every startup.
$run  = New-ScheduledTaskAction -Execute $python -Argument "`"$MonitorDir\monitor.py`"" -WorkingDirectory $MonitorDir
$who  = New-ScheduledTaskPrincipal -UserId SYSTEM -LogonType ServiceAccount -RunLevel Highest
$opts = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask "ScreenTimeMonitor" -Action $run -Trigger (New-ScheduledTaskTrigger -AtStartup) -Principal $who -Settings $opts -Force | Out-Null

# Task 2 -- show the overlay in the child's session when they log in.
$run = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$SharedDir\remaining_time_widget.py`"" -WorkingDirectory $SharedDir
$who = New-ScheduledTaskPrincipal -UserId $childUser -LogonType Interactive
Register-ScheduledTask "ScreenTimeWidget" -Action $run -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $childUser) -Principal $who -Force | Out-Null

if ($generatedSecret) {
    Write-Host "`nShared secret, needed by create_code.py on your own machine:" -ForegroundColor Yellow
    Write-Host "  $generatedSecret"
    Write-Host "  (write it to data\secret.txt there, or set CHILD_SECRET)"
}
Write-Host "`nDone. Monitor starts after a reboot; the widget appears when $childUser logs in."

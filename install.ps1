$ErrorActionPreference = "Stop"
$MonitorDir = "C:\ProgramData\ScreenTime"   # monitor + data; hidden from the child

# Re-launch as administrator if we aren't already.
$admin = [Security.Principal.WindowsBuiltInRole]::Administrator
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole($admin)) {
    Start-Process powershell "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    return
}

# This window closes the moment the script ends, taking any error message with it.
trap { Write-Host "`n$_" -ForegroundColor Red; Read-Host "Press Enter to close" | Out-Null; exit 1 }

$src = $PSScriptRoot

$configText = Get-Content -Raw "$src\config.py"

# Which account is the child's. A typed name invites a typo that would leave the
# monitor watching an account nobody uses, so offer the real ones and check.
$enabledUsers = @(Get-LocalUser | Where-Object { $_.Enabled } | ForEach-Object { $_.Name })
$adminUsers = @()
try {
    $adminUsers = @(Get-LocalGroupMember -SID "S-1-5-32-544" | ForEach-Object { ($_.Name -split '\\')[-1] })   # Administrators -- the SID works in every display language
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

# Both credentials go to files in the locked data folder, never into config.py,
# which git tracks. Asked for now, written only once the folder ACL is in place.
$secretFile = "$MonitorDir\data\secret.txt"
$tokenFile  = "$MonitorDir\data\child_token.txt"
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

$tokenPrompt = "Child token from add_child.py on the parent's server"
if (Test-Path $tokenFile) {
    $tokenPrompt += " (Enter keeps the current one)"
} else {
    $tokenPrompt += " (Enter to run without server syncing)"
}
$childToken = (Read-Host $tokenPrompt).Trim()

# SERVER_URL is a plain variable in config.py, so it's patched into the copy
# installed below -- never into $src\config.py, which git tracks.
$existingServerUrl = ""
if (Test-Path "$MonitorDir\config.py") {
    $existingServerUrl = [regex]::Match([IO.File]::ReadAllText("$MonitorDir\config.py"), 'SERVER_URL\s*=\s*"([^"]*)"').Groups[1].Value
}
$serverUrlPrompt = "Parent's server URL, e.g. https://screentime.example.com"
if ($existingServerUrl) { $serverUrlPrompt += " (Enter keeps $existingServerUrl)" }
else                    { $serverUrlPrompt += " (Enter to run without server syncing)" }
$serverUrl = (Read-Host $serverUrlPrompt).Trim()
if (-not $serverUrl) { $serverUrl = $existingServerUrl }

# Where the "Extra time" shortcut goes. The shared desktop is one file every
# account sees, the parent's included; the child's own Desktop keeps it off yours.
$linkFile = "$MonitorDir\data\link_path.txt"   # so uninstall.ps1 finds a non-default choice
$defaultLinkDir = "$env:PUBLIC\Desktop"
$previousLinkPath = ""
if (Test-Path $linkFile) {
    $previousLinkPath = [IO.File]::ReadAllText($linkFile).Trim()
    if ($previousLinkPath) { $defaultLinkDir = Split-Path $previousLinkPath }
}
$linkDir = (Read-Host "Folder for the 'Extra time' shortcut (Enter for $defaultLinkDir)").Trim().Trim('"')
if (-not $linkDir) { $linkDir = $defaultLinkDir }
if (-not (Test-Path $linkDir -PathType Container)) {
    throw "'$linkDir' is not an existing folder. Create it first, or press Enter for $defaultLinkDir."
}
$linkPath = Join-Path $linkDir "Extra time.lnk"

# Install Python machine-wide if it's missing (the widget needs its bundled tkinter).
# Never trust whatever python.exe is on the admin's PATH: a per-user install under
# that profile is unreadable from the child's account, and the widget task then
# dies with Access Denied.
$targetDir = "C:\Program Files\Python311"
# C:\Python3* is where older runs of this script installed. Kept in the search so
# those machines are found and hardened below rather than given a second Python.
$python = (Get-ChildItem "C:\Program Files\Python3*\python.exe", "C:\Python3*\python.exe" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
if (-not $python) {
    # --scope machine alone isn't enough: if the same version exists per-user,
    # the installer converts it in place instead of installing fresh under
    # Program Files; the explicit TargetDir prevents that.
    # The \" is what carries the space in the path through PowerShell -> winget -> installer.
    $override = '/quiet InstallAllUsers=1 PrependPath=0 TargetDir=\"' + $targetDir + '\"'
    winget install --id Python.Python.3.11 -e --scope machine --accept-package-agreements --accept-source-agreements --override $override
    $python = (Get-ChildItem "$targetDir\python.exe" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
}
if (-not $python) { throw "Could not find or install a machine-wide Python under C:\Program Files." }
$pythonDir = Split-Path $python

# monitor.py runs as SYSTEM on this interpreter, so the child must not be able to
# write into it: a sitecustomize.py or .pth planted in Lib\site-packages would run
# as SYSTEM at every boot. Program Files already forbids that, but a folder at the
# root of C:\ inherits an ACE that lets any user create files inside it.
icacls $pythonDir /inheritance:r /grant "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-32-545:(OI)(CI)RX" | Out-Null   # SYSTEM, Administrators, BUILTIN\Users read-only
if ($LASTEXITCODE -ne 0) { throw "Could not lock $pythonDir; the child could plant code there that runs as SYSTEM." }

$pythonw = Join-Path $pythonDir pythonw.exe   # windowless twin, for the widget

# Monitor folder: copy the files, then lock it to SYSTEM + Administrators only.
# That lock is what stops the child reading data\secret.txt and forging codes.
New-Item -ItemType Directory -Force "$MonitorDir\data" | Out-Null
Copy-Item "$src\monitor.py", "$src\os_tooling.py", "$src\remote_sync.py", "$src\config.py" $MonitorDir -Force
$copiedConfigPath = "$MonitorDir\config.py"
[IO.File]::WriteAllText($copiedConfigPath, [IO.File]::ReadAllText($copiedConfigPath).Replace('SERVER_URL = ""', "SERVER_URL = `"$serverUrl`""))
icacls $MonitorDir /inheritance:r /grant "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" | Out-Null   # S-1-5-18 = SYSTEM, S-1-5-32-544 = Administrators
# icacls signals failure only through its exit code, which $ErrorActionPreference
# does not catch -- unchecked, the secret below lands in a folder the child can read.
if ($LASTEXITCODE -ne 0) { throw "Could not lock $MonitorDir; data\secret.txt would be readable by the child." }

# Written only now, so neither credential ever sits in a folder the child can read.
if ($secretHex)   { Set-Content -Path $secretFile -Value $secretHex   -Encoding ascii -NoNewline }
if ($childToken) { Set-Content -Path $tokenFile  -Value $childToken -Encoding ascii -NoNewline }
# UTF-8 without a BOM, unlike the two above: an account name is not always ascii.
[IO.File]::WriteAllText($userFile, $childUser)

# Shared folder: every local account may write here. It holds only the overlay
# script, the number it shows and the redeem file -- nothing that has to be
# trusted, since the codes inside are signed and checked by monitor.py.
New-Item -ItemType Directory -Force $SharedDir | Out-Null
icacls $SharedDir /grant "*S-1-5-32-545:(OI)(CI)M" | Out-Null   # *S-1-5-32-545 = BUILTIN\Users
Copy-Item "$src\remaining_time_widget.py" $SharedDir -Force
if (-not (Test-Path $redeemFile)) { New-Item -ItemType File $redeemFile | Out-Null }

# The shortcut. An earlier install may have left one in a different folder.
if ($previousLinkPath -and $previousLinkPath -ne $linkPath -and (Test-Path $previousLinkPath)) {
    Remove-Item -LiteralPath $previousLinkPath -Force
}
$link = (New-Object -ComObject WScript.Shell).CreateShortcut($linkPath)
$link.TargetPath = $redeemFile
$link.Save()
[IO.File]::WriteAllText($linkFile, $linkPath)

# Task 1 -- run monitor.py as SYSTEM at every startup.
$run  = New-ScheduledTaskAction -Execute $python -Argument "`"$MonitorDir\monitor.py`"" -WorkingDirectory $MonitorDir
$who  = New-ScheduledTaskPrincipal -UserId SYSTEM -LogonType ServiceAccount -RunLevel Highest
$opts = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask "ScreenTimeMonitor" -Action $run -Trigger (New-ScheduledTaskTrigger -AtStartup) -Principal $who -Settings $opts -Force | Out-Null

# Task 2 -- show the overlay in the child's session when they log in.
$run = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$SharedDir\remaining_time_widget.py`"" -WorkingDirectory $SharedDir
$who = New-ScheduledTaskPrincipal -UserId $childUser -LogonType Interactive
# default task settings would skip the start on battery power
Register-ScheduledTask "ScreenTimeWidget" -Action $run -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $childUser) -Principal $who -Settings $opts -Force | Out-Null

if ($generatedSecret) {
    Write-Host "`nShared secret, needed by create_code.py on your own machine:" -ForegroundColor Yellow
    Write-Host "  $generatedSecret"
    Write-Host "  (write it to data\secret.txt there, or set CHILD_SECRET)"
}
Write-Host "`nDone. Monitor starts after a reboot; the widget appears when $childUser logs in."
Read-Host "`nPress Enter to close" | Out-Null

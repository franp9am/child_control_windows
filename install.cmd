@echo off
rem Windows blocks .ps1 files by default; a .cmd is not subject to that policy,
rem so this hands the script to PowerShell with the same -ExecutionPolicy Bypass
rem install.ps1 already uses to re-launch itself. Nothing on the machine changes.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
@echo off
rem Double-click alternative to the one-liner in bootstrap.ps1, for a parent who
rem would rather not open PowerShell. Downloads that script and runs it; like
rem install.cmd, this only bypasses the execution policy for this one run.
rem Windows marks a downloaded .cmd as untrusted: click "More info", "Run anyway".
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/franp9am/child_control_windows/master/bootstrap.ps1 | iex"
if errorlevel 1 pause

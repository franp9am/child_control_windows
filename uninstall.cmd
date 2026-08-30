@echo off
rem See install.cmd. %* passes -KeepData through.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1" %*
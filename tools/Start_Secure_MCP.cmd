@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0secure_mcp.ps1" -Action start
if errorlevel 1 pause

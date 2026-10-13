@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\open_flash.ps1"
  exit /b
)
if exist "%~dp0python\python.exe" (
  "%~dp0python\python.exe" -X utf8 "%~dp0tools\flash_esp32.py" %*
) else (
  python -X utf8 "%~dp0tools\flash_esp32.py" %*
)
set "flash_result=%errorlevel%"
exit /b %flash_result%

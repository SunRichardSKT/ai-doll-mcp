@echo off
setlocal
if exist "%~dp0python\pythonw.exe" (
    start "" "%~dp0python\pythonw.exe" -X utf8 "%~dp0tools\control_panel.py" --autostart %*
    exit /b
)
start "" /b powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0tools\open_control_panel.ps1" -AutoStart %*

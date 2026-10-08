param(
    [string]$Port='COM3',
    [ValidateSet('saved','usb','wifi')][string]$Transport='saved',
    [string]$DeviceHost='',
    [switch]$Background
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$python=Join-Path $root '.venv\Scripts\python.exe'
if(!(Test-Path $python)){$python=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'}
if(!(Test-Path $python)){$python=(Get-Command python -ErrorAction Stop).Source}
$env:DOLL_SERIAL_PORT=$Port
$env:DOLL_DEVICE_HOST=$DeviceHost
$env:DOLL_TRANSPORT=if($Transport -eq 'saved'){''}else{$Transport}
if($DeviceHost -and $Transport -eq 'usb'){throw 'DeviceHost cannot be used with USB transport'}
if($Background){
    $entry=Join-Path $PSScriptRoot 'run_background.py'
    Start-Process -FilePath $python -ArgumentList ('"'+$entry+'"') -WorkingDirectory $root -WindowStyle Hidden
    Write-Output 'Open http://127.0.0.1:8768 ; background logs: build/device-lab/background-service.log'
}else{
    & $python (Join-Path $PSScriptRoot 'device_setup_server.py')
}

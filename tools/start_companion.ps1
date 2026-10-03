param(
    [string]$Port='COM3',
    [ValidateSet('saved','usb','wifi')][string]$Transport='saved',
    [string]$DeviceHost=''
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
& $python (Join-Path $PSScriptRoot 'device_setup_server.py')

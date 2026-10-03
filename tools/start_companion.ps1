param([string]$Port='COM3')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$python=Join-Path $root '.venv\Scripts\python.exe'
if(!(Test-Path $python)){$python=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'}
if(!(Test-Path $python)){$python=(Get-Command python -ErrorAction Stop).Source}
$env:DOLL_SERIAL_PORT=$Port
& $python (Join-Path $PSScriptRoot 'device_setup_server.py')

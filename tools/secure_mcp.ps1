param(
    [ValidateSet('install','configure','start','status','stop','reset-address')][string]$Action='start',
    [string]$DeviceHost=''
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$python=Join-Path $root '.venv\Scripts\python.exe'
if($Action -in @('install','start','configure')){
    & (Join-Path $PSScriptRoot 'open_control_panel.ps1') -AutoStart:($Action -eq 'start')
}else{
    if(!(Test-Path -LiteralPath $python)){throw 'Open AI_Doll.cmd and prepare the runtime environment first.'}
    & $python (Join-Path $PSScriptRoot 'secure_mcp.py') $Action
    if($LASTEXITCODE -ne 0){throw 'Secure MCP operation failed.'}
}

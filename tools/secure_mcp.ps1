param(
    [ValidateSet('install','configure','start','status','stop','reset-address')][string]$Action='start',
    [string]$DeviceHost=''
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$python=Join-Path $root '.venv\Scripts\python.exe'
if($Action -eq 'install' -or !(Test-Path -LiteralPath $python)){
    if(!(Test-Path -LiteralPath $python)){
        $pythonCommand=Get-Command python -ErrorAction SilentlyContinue
        if(!$pythonCommand){throw 'Install Python 3.12 from python.org, then run this installer again.'}
        & $pythonCommand.Source -I -m venv (Join-Path $root '.venv')
        if($LASTEXITCODE -ne 0){throw 'Python environment creation failed.'}
    }
    & $python -I -c 'import sys; assert sys.version_info >= (3,12), "Python 3.12 or later is required"'
    if($LASTEXITCODE -ne 0){throw 'Python 3.12 or later is required.'}
    & $python -I -m pip install -r (Join-Path $root 'requirements-companion.txt')
    if($LASTEXITCODE -ne 0){throw 'Dependency installation failed.'}
    & $python (Join-Path $PSScriptRoot 'install_tunnel_client.py')
    if($LASTEXITCODE -ne 0){throw 'Official tunnel client verification failed.'}
}
if($Action -in @('install','start','configure')){
    $pairing=Join-Path $root 'build\device-lab\device-private.json'
    if(!(Test-Path -LiteralPath $pairing) -and !$DeviceHost){
        $DeviceHost=Read-Host 'Enter the ESP32 Wi-Fi IPv4 address shown on its settings page'
        if(!$DeviceHost){throw 'Wi-Fi pairing is required for a new installation.'}
    }
    $bridgeArguments=@{SkipDependencies=$true;Transport='saved'}
    if($DeviceHost){$bridgeArguments.DeviceHost=$DeviceHost}
    & (Join-Path $PSScriptRoot 'install_bridge.ps1') @bridgeArguments
    if($LASTEXITCODE -ne 0){throw 'Local collector installation failed.'}
    $ui=Join-Path $PSScriptRoot 'secure_mcp_gui.py'
    $uiArguments=@($ui)
    if($Action -eq 'start'){$uiArguments+='--autostart'}
    & $python @uiArguments
}else{
    & $python (Join-Path $PSScriptRoot 'secure_mcp.py') $Action
}
if($LASTEXITCODE -ne 0){throw 'Secure MCP operation failed.'}

param(
    [ValidateSet('configure','download','start','status','stop','reset-address','verify','address')][string]$Action='start',
    [ValidateSet('status','history','interaction')][string]$Profile='interaction',
    [switch]$Local,
    [switch]$ClientManaged,
    [string]$PythonExecutable=''
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$python=$PythonExecutable
if(!$python){$python=Join-Path $root '.venv\Scripts\python.exe'}
if(!(Test-Path -LiteralPath $python)){$python=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'}
if(!(Test-Path -LiteralPath $python)){$python=(Get-Command python -ErrorAction Stop).Source}
if($Action -eq 'start'){
    $collectorReady=$false
    try{$response=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8768/bridge' -TimeoutSec 2;$collectorReady=$response.StatusCode -eq 200}catch{}
    if(!$collectorReady){
        & (Join-Path $PSScriptRoot 'install_bridge.ps1') -SkipDependencies -AutoDetectDevice
        if(!$?){throw 'Local collector startup failed'}
    }
}
$arguments=@((Join-Path $PSScriptRoot 'deploy_mcp.py'),$Action,'--profile',$Profile)
if($Local){$arguments+='--local'}
if($ClientManaged){$arguments+='--client-managed'}
& $python @arguments
if($LASTEXITCODE -ne 0){throw 'Remote MCP operation failed; see docs/REMOTE_MCP.md'}

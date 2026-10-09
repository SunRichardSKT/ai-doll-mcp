param(
    [ValidateSet('generic','claude-desktop','chatgpt-work','api')][string]$Platform='generic',
    [string]$Port='COM3',
    [ValidateSet('saved','usb','wifi')][string]$Transport='saved',
    [string]$DeviceHost='',
    [switch]$SkipDependencies,
    [switch]$NoStart
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
if($DeviceHost -and $Transport -eq 'usb'){throw 'DeviceHost cannot be used with USB transport'}
$python=Join-Path $root '.venv\Scripts\python.exe'
if($SkipDependencies){
    if(!(Test-Path -LiteralPath $python)){$python=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'}
    if(!(Test-Path -LiteralPath $python)){$python=(Get-Command python -ErrorAction Stop).Source}
}else{
    if(!(Test-Path -LiteralPath $python)){
        $basePython=(Get-Command python -ErrorAction Stop).Source
        & $basePython -m venv (Join-Path $root '.venv')
        if($LASTEXITCODE -ne 0){throw 'Python environment creation failed'}
    }
    & $python -m pip install -r (Join-Path $root 'requirements-companion.txt')
    if($LASTEXITCODE -ne 0){throw 'Dependency installation failed'}
}
& $python (Join-Path $PSScriptRoot 'install_companion_mcp.py')
if($LASTEXITCODE -ne 0){throw 'MCP configuration generation failed'}
$work=Join-Path $root 'build\device-lab'
$config=[ordered]@{
    bridge_version='2.12.2';platform=$Platform;serial_port=$Port
    transport=$Transport;device_host=$DeviceHost
    local_page='http://127.0.0.1:8768/bridge'
    native_mcp_events='http://127.0.0.1:8768/bridge/mcp'
    event_protocol='2026-07-28'
    mcp_config=(Join-Path $work 'mcp-client-config.json')
    guide=(Join-Path $root 'docs\PROACTIVE_INTERACTION.md')
}
$config | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $work 'bridge-install.json') -Encoding utf8
if(!$NoStart){
    $alreadyRunning=$false
    try{$response=Invoke-WebRequest -Uri 'http://127.0.0.1:8768/bridge' -TimeoutSec 2;$alreadyRunning=$response.StatusCode -eq 200}catch{}
    if($alreadyRunning -and ($Transport -ne 'saved' -or $DeviceHost)){
        $collectorPrivate=Get-Content -LiteralPath (Join-Path $work 'companion-private.json') -Raw | ConvertFrom-Json
        try{$currentConnection=Invoke-RestMethod -Uri 'http://127.0.0.1:8768/connection' -Headers @{Authorization=('Bearer '+$collectorPrivate.token)} -TimeoutSec 2}
        catch{throw 'The running service must be restarted to activate Wi-Fi support.'}
        $wantedTransport=if($DeviceHost){'wifi'}else{$Transport}
        if($currentConnection.transport -ne $wantedTransport -or ($DeviceHost -and $currentConnection.device_host -ne $DeviceHost)){
            throw 'The running service uses a different device connection. Close this project service and run tools/start_companion.ps1 with the requested DeviceHost or Transport.'
        }
    }
    if(!$alreadyRunning){
        try{Invoke-WebRequest -Uri 'http://127.0.0.1:8768/' -TimeoutSec 2 | Out-Null;throw 'An older service is running on port 8768. Close it before installing the updated bridge.'}
        catch{if($_.Exception.Message -like 'An older service*'){throw}}
        $env:DOLL_SERIAL_PORT=$Port
        $env:DOLL_DEVICE_HOST=$DeviceHost
        $env:DOLL_TRANSPORT=if($Transport -eq 'saved'){''}else{$Transport}
        $stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
        $process=Start-Process -FilePath $python -ArgumentList ('"'+(Join-Path $PSScriptRoot 'device_setup_server.py')+'"') -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $work "bridge-$stamp.out.log") -RedirectStandardError (Join-Path $work "bridge-$stamp.err.log") -PassThru
        $started=$false
        for($attempt=0;$attempt -lt 20;$attempt++){
            try{Invoke-WebRequest -Uri 'http://127.0.0.1:8768/bridge' -TimeoutSec 1 | Out-Null;$started=$true;break}catch{}
            if($process.HasExited){throw 'Bridge failed to start; inspect its local error log'}
            Start-Sleep -Milliseconds 500
        }
        if(!$started){throw 'Bridge startup timed out; inspect its local error log'}
    }
}
if($NoStart){Write-Output ('Configuration ready for '+$Platform+'. Open http://127.0.0.1:8768/bridge after starting the service.')}
else{Write-Output ('Service ready for '+$Platform+'. Open http://127.0.0.1:8768/bridge.')}
Write-Output 'An already running service keeps its current transport. To change USB/Wi-Fi, close this project service and run tools/start_companion.ps1 with DeviceHost or Transport.'
Write-Output ('MCP configuration: '+(Join-Path $work 'mcp-client-config.json'))
Write-Output ('Integration guide: '+$config.guide)
Write-Output ('Existing conversation guide: '+(Join-Path $root 'docs\EXISTING_CHAT.md'))
Write-Output 'Continue in your existing AI conversation. If supported, choose the doll_chat_companion MCP prompt; no second model API key is needed.'
Write-Output 'Client account settings are unchanged. ChatGPT Events needs a supported Work chat and an authenticated remote connection/tunnel; custom API apps provide their own model callback.'

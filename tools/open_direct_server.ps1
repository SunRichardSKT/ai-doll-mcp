param([switch]$NoBrowser,[ValidateRange(1024,65535)][int]$Port=8781,[switch]$Stop)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'runtime_python.ps1')
try {
    $python=Get-DollPython -Root $root
    $arguments=@('-X','utf8',(Join-Path $PSScriptRoot 'start_direct_server.py'),'--port',"$Port")
    if($NoBrowser){$arguments+='--no-browser'}
    if($Stop){$arguments+='--stop'}
    & $python @arguments
    if($LASTEXITCODE -ne 0){throw 'Server startup failed'}
}catch{
    if($NoBrowser){throw}
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show('服务端未能启动。请完整解压软件包到可写目录，保留 python 文件夹，并检查 8781 端口是否被占用。','AI Doll · 服务端','OK','Error') | Out-Null
}

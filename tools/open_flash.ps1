param([int]$Port=8770,[switch]$NoBrowser)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'runtime_python.ps1')
$python=Get-DollPython -Root $root
$flashArgs=@('-X','utf8',('"'+(Join-Path $PSScriptRoot 'flash_server.py')+'"'),'--port',[string]$Port)
if($NoBrowser){$flashArgs+='--no-browser'}
Start-Process -FilePath $python -ArgumentList $flashArgs -WorkingDirectory $root -WindowStyle Hidden

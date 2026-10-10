param([switch]$SkipDependencies,[string]$DeviceHost='',[switch]$ConfigureSakura)
$ErrorActionPreference='Stop'
$arguments=@{AutoDetectDevice=$true;VerifyConnection=$true}
if($SkipDependencies){$arguments.SkipDependencies=$true}
if($DeviceHost){$arguments.DeviceHost=$DeviceHost;$arguments.Transport='wifi'}
& (Join-Path $PSScriptRoot 'install_bridge.ps1') @arguments
if(!$?){throw 'Local installation failed'}
& (Join-Path $PSScriptRoot 'remote_mcp.ps1') -Action download
if($ConfigureSakura){& (Join-Path $PSScriptRoot 'remote_mcp.ps1') -Action configure}
Write-Output 'Local installation is ready. Complete Sakura first-time configuration, then use tools/remote_mcp.ps1 -Action start.'

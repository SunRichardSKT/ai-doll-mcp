param([switch]$Upload,[string]$Port='COM3')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$python=Join-Path $root '.venv\Scripts\python.exe'
if(!(Test-Path $python)){$python=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'}
if(!(Test-Path $python)){$python=(Get-Command python -ErrorAction Stop).Source}
$oldPythonPath=$env:PYTHONPATH
$oldPio=$env:PLATFORMIO_CORE_DIR
$mapped=$null
try {
 foreach($letter in @('Z','Y','X','W','V','U','T')) {
  if(!(Test-Path "${letter}:\")) {$mapped="${letter}:"; & subst.exe $mapped $root; if($LASTEXITCODE -ne 0){throw 'Drive mapping failed'}; break}
 }
 if(!$mapped){throw 'No free drive alias'}
 $env:PYTHONPATH="$mapped\.tools\python-packages"
 if($oldPythonPath){$env:PYTHONPATH+=";$oldPythonPath"}
 $env:PLATFORMIO_CORE_DIR="$mapped\.tools\platformio"
 $argsPio=@('-m','platformio','run','-d',"$mapped\firmware",'-e','supermini-lab')
 if($Upload){$argsPio+=@('-t','upload','--upload-port',$Port)}
 & $python @argsPio
 if($LASTEXITCODE -ne 0){throw 'Lab firmware build/upload failed'}
} finally {
 $env:PYTHONPATH=$oldPythonPath;$env:PLATFORMIO_CORE_DIR=$oldPio
 if($mapped){& subst.exe $mapped /d}
}

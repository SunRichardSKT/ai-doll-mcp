param([switch]$AutoStart,[switch]$NoBrowser,[ValidateRange(1024,65535)][int]$PanelPort=8769)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
Add-Type -AssemblyName PresentationFramework
try {
    $candidates=@((Join-Path $root 'python\python.exe'),(Join-Path $root '.venv\Scripts\python.exe'))
    $command=Get-Command python -ErrorAction SilentlyContinue
    if($command){$candidates+=$command.Source}
    $launcher=Get-Command py -ErrorAction SilentlyContinue
    if($launcher){
        $found=& $launcher.Source -3.12 -c 'import sys; print(sys.executable)' 2>$null
        if($LASTEXITCODE -eq 0){$candidates+=$found}
    }
    $candidates+=@(Get-ChildItem -LiteralPath (Join-Path $env:LOCALAPPDATA 'Programs\Python') -Filter python.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
    $python=$null
    foreach($candidate in ($candidates | Select-Object -Unique)){
        if(!(Test-Path -LiteralPath $candidate)){continue}
        & $candidate -I -c 'import sys,struct; assert (3,12)<=sys.version_info[:2]<(3,15) and struct.calcsize(chr(80))==8' 2>$null
        if($LASTEXITCODE -eq 0){$python=$candidate;break}
    }
    if(!$python){
        [System.Windows.MessageBox]::Show('运行环境缺失。请完整解压 Windows 软件包，保留根目录 python 文件夹，然后双击 AI_Doll.cmd。无需另行安装 Python。','AI Doll · 准备运行环境','OK','Information') | Out-Null
        exit 1
    }
    $pythonw=Join-Path (Split-Path -Parent $python) 'pythonw.exe'
    if(!(Test-Path -LiteralPath $pythonw)){$pythonw=$python}
    $arguments='-X utf8 "'+(Join-Path $PSScriptRoot 'control_panel.py')+'"'
    if($AutoStart){$arguments+=' --autostart'}
    $arguments+=' --port '+$PanelPort
    if($NoBrowser){$arguments+=' --no-browser'}
    Start-Process -FilePath $pythonw -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden
}catch{
    [System.Windows.MessageBox]::Show('管理中心未能打开。请完整解压 Windows 软件包到可写目录，并确认根目录 python 文件夹完整。无需另行安装 Python。','AI Doll · 启动失败','OK','Error') | Out-Null
    exit 1
}

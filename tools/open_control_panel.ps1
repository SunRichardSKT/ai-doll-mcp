param([switch]$AutoStart)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
Add-Type -AssemblyName PresentationFramework
try {
    $candidates=@((Join-Path $root '.venv\Scripts\python.exe'))
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
        & $candidate -I -c 'import sys,struct; assert (3,12)<=sys.version_info[:2]<(3,15) and struct.calcsize("P")==8' 2>$null
        if($LASTEXITCODE -eq 0){$python=$candidate;break}
    }
    if(!$python){
        $answer=[System.Windows.MessageBox]::Show('需要 Windows 64 位 Python 3.12–3.14。点击“确定”打开官方下载页，安装时勾选 Add Python to PATH，然后重新打开 AI_Doll.cmd。其余依赖会由管理中心自动准备。','AI Doll · 准备运行环境','OKCancel','Information')
        if($answer -eq 'OK'){Start-Process 'https://www.python.org/downloads/windows/'}
        exit 1
    }
    $pythonw=Join-Path (Split-Path -Parent $python) 'pythonw.exe'
    if(!(Test-Path -LiteralPath $pythonw)){$pythonw=$python}
    $arguments='-X utf8 "'+(Join-Path $PSScriptRoot 'control_panel.py')+'"'
    if($AutoStart){$arguments+=' --autostart'}
    Start-Process -FilePath $pythonw -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden
}catch{
    [System.Windows.MessageBox]::Show('管理中心未能打开。请确认项目已完整解压到可写目录，并安装 Windows 64 位 Python 3.12–3.14。','AI Doll · 启动失败','OK','Error') | Out-Null
    exit 1
}

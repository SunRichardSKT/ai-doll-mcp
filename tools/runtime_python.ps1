# Prefer the interpreter included in the root of the Windows software package.
function Get-DollPython {
    param([string]$Root)
    foreach($relative in @('python\python.exe','.venv\Scripts\python.exe')){
        $candidate=Join-Path $Root $relative
        if(Test-Path -LiteralPath $candidate -PathType Leaf){return $candidate}
    }
    $command=Get-Command python -ErrorAction SilentlyContinue
    if($command){return $command.Source}
    throw '运行环境缺失。请完整解压 Windows 软件包并保留根目录 python 文件夹。'
}

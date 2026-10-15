param([string]$ListenHost = '', [int]$Port = 8775, [switch]$Demo)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot 'runtime_python.ps1')
$runtime = Get-DollPython -Root $root
if (-not $ListenHost) {
    $addresses = @(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
        $_.IPAddress -match '^(192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.)' -and
        $_.AddressState -eq 'Preferred'
    })
    if (-not $addresses.Count) { throw '未找到局域网地址。请先把电脑和手机接入同一个家庭网络。' }
    Write-Host '请选择手机能够访问的电脑局域网地址：'
    for ($i=0; $i -lt $addresses.Count; $i++) {
        Write-Host "$($i+1). $($addresses[$i].InterfaceAlias) $($addresses[$i].IPAddress)"
    }
    if ($addresses.Count -eq 1) { $ListenHost=$addresses[0].IPAddress }
    else {
        $choice=0
        if (-not [int]::TryParse((Read-Host '输入编号'),[ref]$choice) -or $choice -lt 1 -or $choice -gt $addresses.Count) {
            throw '请输入列表中的编号。'
        }
        $ListenHost=$addresses[$choice-1].IPAddress
    }
}
Write-Host '下面的完整 MCP 地址填到手机，不是网页设置地址。'
Write-Host '此窗口运行期间服务可用；Ctrl+C 停止。原管理页和 Secure 连接不受影响。'
if ($Demo) {
    Write-Host '当前为独立模拟演示：不读取开发板，不修改真实历史和校准。'
    & $runtime -X utf8 (Join-Path $PSScriptRoot 'operit_demo.py') --listen-host $ListenHost --port $Port
} else {
    Write-Host '真实设备模式：先用 AI_Doll.cmd 启动采集服务，并在设置中启用主动回应。'
    & $runtime -X utf8 (Join-Path $PSScriptRoot 'remote_mcp.py') --listen-host $ListenHost --port $Port --profile interaction --folder (Join-Path $root 'build\device-lab\operit-mcp') --print-address
}
if ($LASTEXITCODE -ne 0) { throw 'Operit MCP 服务未启动。请检查地址、端口或已有同名服务。' }

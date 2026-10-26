#Requires -Version 5.1
<#
  qq-bridge · 阿里云 Windows Server 一键部署
  用法（在服务器 PowerShell 里粘贴一行，改掉参数）：

  powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy-aliyun.ps1 `
    -QQ "10001" -Allow "20002" `
    -BaseUrl "https://api.deepseek.com/v1" -ApiKey "sk-xxx" -Model "deepseek-chat" `
    -Name "小柚" -Age 20 -Who "在奶茶店做兼职" `
    -Style "短句、爱用呀啦，会撒娇也会损人" `
    -Relation "高中同学，她暗恋我三年没说出口" -City "杭州"

  做四件事：下载安装包 → 装环境 → 写配置 → 起服务并给出二维码
#>
param(
    [Parameter(Mandatory = $true)][string]$QQ,
    [Parameter(Mandatory = $true)][string[]]$Allow,
    [Parameter(Mandatory = $true)][string]$BaseUrl,
    [Parameter(Mandatory = $true)][string]$ApiKey,
    [Parameter(Mandatory = $true)][string]$Model,
    [string]$Name = "小柚",
    [int]$Age = 20,
    [string]$Who = "普通上班族",
    [string]$Style = "短句、口语，不说书面语",
    [string]$Relation = "",
    [string]$City = "",
    [string]$PersonaPrompt = "",
    [switch]$SkipStart
)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Say($m, $c = 'Gray') { Write-Host $m -ForegroundColor $c }
function Step($n, $m) { Write-Host "`n[$n] $m" -ForegroundColor Cyan }

$Root = "D:\qqbridge"
$ZipUrl = "https://gitee.com/wangcc111/qq-bridge-dist/releases/download/v1.0/qq-bridge-full.zip"

Say "==============================================" Cyan
Say "   qq-bridge 阿里云部署" Cyan
Say "==============================================" Cyan
Say "系统：$([Environment]::OSVersion.VersionString)"

# ---------- 1. 安装包 ----------
Step 1 "下载安装包（35MB）"
$pkg = "D:\qq-bridge-full.zip"
if (Test-Path $pkg) {
    Say "  已存在，跳过下载"
} else {
    Invoke-WebRequest -Uri $ZipUrl -OutFile $pkg -UseBasicParsing -TimeoutSec 900
    Say "  已下载 $([math]::Round((Get-Item $pkg).Length/1MB,1)) MB" Green
}
if (Test-Path $Root) {
    Say "  $Root 已存在：只更新代码，保留配置和记忆"
    $tmp = "D:\_qqbridge_new"
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Expand-Archive -Path $pkg -DestinationPath "D:\_unz" -Force
    $inner = (Get-ChildItem "D:\_unz" -Directory | Select-Object -First 1).FullName
    Move-Item $inner $tmp
    foreach ($item in @("qqbot", "docs", "scripts", "tools", "tests")) {
        if (Test-Path (Join-Path $tmp $item)) {
            Copy-Item (Join-Path $tmp $item) $Root -Recurse -Force
        }
    }
    Get-ChildItem $tmp -File | Where-Object { $_.Extension -in @('.py', '.bat', '.vbs', '.ps1', '.md', '.yaml') } |
        ForEach-Object { Copy-Item $_.FullName $Root -Force }
    Remove-Item $tmp, "D:\_unz" -Recurse -Force -ErrorAction SilentlyContinue
    Say "  代码已更新" Green
} else {
    Expand-Archive -Path $pkg -DestinationPath "D:\_unz" -Force
    $inner = (Get-ChildItem "D:\_unz" -Directory | Select-Object -First 1).FullName
    Move-Item $inner $Root
    Remove-Item "D:\_unz" -Recurse -Force -ErrorAction SilentlyContinue
    Say "  已解压到 $Root" Green
}
Set-Location $Root

# ---------- 2. 浏览器（服务器默认没有，扫码窗口需要） ----------
Step 2 "检查浏览器（扫码窗口要用）"
$edge = "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
if (-not (Test-Path $edge)) {
    Say "  没有 Edge，尝试安装…" Yellow
    try {
        winget install --id Microsoft.Edge -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
        Say "  Edge 已安装" Green
    } catch {
        Say "  自动安装失败。手动装一下 Edge，或改用 NapCat WebUI 手动看二维码。" Yellow
        Say "  下载：https://www.microsoft.com/edge/business/download" Yellow
    }
} else { Say "  Edge 已存在" Green }

# ---------- 3. 环境 ----------
Step 3 "安装 Python 环境和依赖"
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "install.ps1")
if (-not (Test-Path (Join-Path $Root ".venv\Scripts\python.exe"))) {
    Say "  环境安装失败，停止" Red; exit 1
}

# ---------- 4. 工单 ----------
Step 4 "写配置"
$ticket = @"
robot:
  qq: "$QQ"

allow:
$($Allow | ForEach-Object { "  - `"$_`"" } | Out-String)

city: "$City"

api:
  base_url: "$BaseUrl"
  api_key: "$ApiKey"
  model: "$Model"

persona:
  name: "$Name"
  age: $Age
  who: "$Who"
  style: "$Style"
  relation: "$Relation"
  prompt: |
$($PersonaPrompt -split "`n" | ForEach-Object { "    $_" } | Out-String)
"@
$ticket = $ticket -replace "(\r?\n){3,}", "`n`n"
Set-Content -Path (Join-Path $Root "ticket.yaml") -Value $ticket -Encoding UTF8
Say "  已写 ticket.yaml" Green

$py = Join-Path $Root ".venv\Scripts\python.exe"
& $py (Join-Path $Root "autoconfig.py") --ticket "ticket.yaml"
if ($LASTEXITCODE -ne 0) { Say "  配置生成失败，检查 ticket.yaml" Red; exit 1 }

# ---------- 5. 启动 ----------
Step 5 "启动服务"
Get-NetTCPConnection -LocalPort 8088 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Start-Sleep 2
Start-Process -FilePath (Join-Path $Root ".venv\Scripts\pythonw.exe") `
    -ArgumentList "boot.py" -WorkingDirectory $Root
Say "  已启动，等 40 秒建立连接…"
Start-Sleep 40

$status = ""
try { $status = (Invoke-WebRequest "http://127.0.0.1:8088/status" -UseBasicParsing -TimeoutSec 10).Content } catch { }
if ($status -match '"connected":\s*true') {
    Say "  已连接：$status" Green
} else {
    Say "  还没连上，走扫码登录" Yellow
    Say "  屏幕上会打开一个二维码窗口，用手机 QQ 扫"
    Start-Process -FilePath $py -ArgumentList "login_qr.py" -WorkingDirectory $Root
    for ($i = 0; $i -lt 18; $i++) {
        Start-Sleep 10
        try { $status = (Invoke-WebRequest "http://127.0.0.1:8088/status" -UseBasicParsing -TimeoutSec 10).Content } catch { }
        if ($status -match '"connected":\s*true') { Say "  扫码成功，已连接" Green; break }
    }
}

# ---------- 6. 自检 ----------
Step 6 "自检"
& $py (Join-Path $Root "selfcheck.py")

Step 7 "完成"
Say ""
Say "部署目录：$Root" Green
Say "机器人 QQ：$QQ" Green
Say "白名单：$($Allow -join ', ')" Green
Say "模型：$Model @ $BaseUrl" Green
Say ""
Say "以后操作：" 
Say "  - 双击桌面「QQ机器人」= 控制面板（启动/扫码/自动修复/备份）"
Say "  - 掉线会自动重登；实在不行就点「扫码登录」再扫一次"
Say "  - 日志：$Root\logs\qq-bridge.log"

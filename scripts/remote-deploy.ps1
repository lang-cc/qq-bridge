#Requires -Version 5.1
<#
.SYNOPSIS
  qq-bridge 远程代装脚本（Windows 10/11，全程无人值守，装完只剩手机扫码）

.DESCRIPTION
  给「远程操控客户电脑帮人部署」用：一条命令装完，自己打印验收报告。
  幂等：重复跑不会重复下载、不会覆盖已有 config.yaml / data / 记忆库。

.EXAMPLE
  # 最基本：把包和解压出来的目录一起带过去，在目录里执行
  powershell -ExecutionPolicy Bypass -File scripts\remote-deploy.ps1 `
      -Qq 10001 -Users 20002 -BaseUrl https://api.deepseek.com/v1 `
      -ApiKey sk-xxx -Model deepseek-chat -PersonaName 小柚

.EXAMPLE
  # 连压缩包一起自动解压安装（操作手只需送一个 zip + 一条命令）
  powershell -ExecutionPolicy Bypass -File deploy.ps1 -ZipPath D:\qq-bridge-full.zip `
      -Qq 10001 -Users 20002 -BaseUrl https://api.deepseek.com/v1 -ApiKey sk-xxx -Model deepseek-chat

.NOTES
  非必需参数都有合理默认；装完输出「远程验收报告」，可直接贴给客户/记录。
#>

[CmdletBinding()]
param(
    # ---- 客户信息（必填；如果给了 -TicketPath，下面这些都可以不填）----
    [string]$Qq,
    [string]$Users,                                        # 白名单，逗号分隔：20002,20003
    [string]$Groups = "",                                  # 群号，逗号分隔（可选）
    [string]$City = "",

    # ---- 模型（必填）----
    [string]$BaseUrl,
    [string]$ApiKey,
    [string]$Model,

    # ---- 人格（可选）----
    [string]$PersonaName = "小柚",
    [int]$PersonaAge = 20,
    [string]$PersonaWho = "普通上班族",
    [string]$PersonaStyle = "短句、口语，不说书面语，不用 markdown",
    [string]$PersonaRelation = "",
    [string]$PersonaPrompt = "",                           # 直接给整段人格（多行），给了就不再用上面几个字段拼

    # ---- 装到哪 / 端口（一般不用改）----
    [string]$InstallDir = "",
    [string]$TicketPath = "",                              # 已有 ticket.yaml 的路径（给了就用它，忽略上面的人格参数）
    [int]$Port = 8199,                                     # NapCat → NoneBot 反向 WS
    [int]$ApiPort = 8088,                                  # 本机 HTTP 接口 + 网页配置台

    # ---- 开关 ----
    [string]$ZipPath = "",                                 # 给一个 zip，自动解压到 InstallDir
    [switch]$SkipNapCat,                                   # 只装环境，不搞 NapCat（已有协议端时用）
    [switch]$NoStart,                                      # 装完不启动（只做环境）
    [switch]$NoShortcut,                                   # 不创建桌面图标（测试 / 多开时用）
    [switch]$DryRun                                        # 只打印计划，不动手
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# ------------------------------------------------------------------ 小工具
function Say($msg, $color = 'Gray') { Write-Host $msg -ForegroundColor $color }
function Step($n, $msg) { Write-Host "`n[$n] $msg" -ForegroundColor Cyan }
function Ok($msg) { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "  ! $msg" -ForegroundColor Yellow }
function Die($msg) { Write-Host "  ✗ $msg" -ForegroundColor Red; exit 1 }
function Have($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

$report = New-Object System.Collections.ArrayList
function Report($line) { [void]$report.Add($line) }

# 必填校验：用 -TicketPath 时这些都可以省
if (-not $TicketPath) {
    $missing = @()
    foreach ($pair in @(
            @('Qq', $Qq), @('Users', $Users), @('BaseUrl', $BaseUrl), @('ApiKey', $ApiKey), @('Model', $Model)
        )) {
        if (-not $pair[1]) { $missing += "-$($pair[0])" }
    }
    if ($missing.Count -gt 0) {
        Write-Host "缺少参数：$($missing -join '、')" -ForegroundColor Red
        Write-Host "要么补齐这些参数，要么用 -TicketPath 指定一份写好的 ticket.yaml" -ForegroundColor Red
        exit 1
    }
}

Say "==============================================" Cyan
Say "   qq-bridge 远程代装（NoneBot2 框架版）" Cyan
Say "==============================================" Cyan

# ------------------------------------------------------------------ 0. 定位安装目录
$here = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Definition }
if (-not $InstallDir) {
    # 脚本在 <根>\scripts\ 下 → 根目录就是安装目录
    if (Test-Path (Join-Path (Split-Path -Parent $here) "nb")) {
        $InstallDir = Split-Path -Parent $here
    } elseif (Test-Path (Join-Path $here "nb")) {
        $InstallDir = $here
    } else {
        $InstallDir = "C:\qqbridge"
    }
}
Say "安装目录：$InstallDir"
Say "机器人 QQ：$Qq    白名单：$Users"

if ($DryRun) {
    Step "DRY-RUN" "只打印计划，不执行任何安装动作"
    Say "  1) 解压 $ZipPath → $InstallDir（如给了 zip）"
    Say "  2) 建 .venv 并 pip install -r requirements.txt（清华源）"
    Say "  3) 下载 NapCat 到 $InstallDir\napcat（除非 -SkipNapCat）"
    Say "  4) 生成 ticket.yaml 并跑 autoconfig.py → config.yaml + data\personas.yaml"
    Say "  5) main_nb.py 首次启动自动生成 nb.env（DRIVER=~fastapi，PORT=$Port）"
    Say "  6) 桌面快捷方式「QQ机器人」+ 启动服务 + 等 /status 通"
    exit 0
}

# ------------------------------------------------------------------ 1. 解压安装包
if ($ZipPath) {
    Step "1/9 解压安装包"
    if (-not (Test-Path $ZipPath)) { Die "找不到 $ZipPath" }
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    $tmp = Join-Path $env:TEMP ("qqb-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
    Expand-Archive -Path $ZipPath -DestinationPath $tmp -Force
    $inner = Get-ChildItem $tmp -Directory | Select-Object -First 1
    $src = if ($inner -and (Test-Path (Join-Path $inner.FullName "main_nb.py"))) { $inner.FullName } else { $tmp }
    Copy-Item (Join-Path $src "*") $InstallDir -Recurse -Force
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Ok "已解压到 $InstallDir"
} else {
    Step "1/9 检查代码目录"
    if (-not (Test-Path (Join-Path $InstallDir "main_nb.py"))) {
        Die "目录里没有 main_nb.py。要么用 -ZipPath 指定安装包，要么在解压后的目录里运行本脚本。"
    }
    Ok "代码齐全"
}
Set-Location $InstallDir

# ------------------------------------------------------------------ 2. Python
Step "2/9 检查 Python（3.10+）"
$py = $null
foreach ($cand in @(@('py', '-3.12'), @('py', '-3'), @('python'), @('python3'))) {
    if (-not (Have $cand[0])) { continue }
    try {
        $ver = & $cand[0] @($cand[1..($cand.Length - 1)]) -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $ver -match '^3\.(\d+)$' -and [int]$Matches[1] -ge 10) {
            $py = $cand
            Ok "Python $ver（$($cand -join ' ')）"
            break
        }
    } catch { }
}
if (-not $py) {
    Warn "没找到 Python 3.10+，尝试 winget 安装 3.12…"
    if (-not (Have winget)) { Die "没有 winget。请手动装 Python 3.12（勾 Add to PATH）后重跑。" }
    winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
    $py = @('py', '-3.12')
    Ok "Python 3.12 已安装"
}
Report ("Python: " + ($py -join ' '))

# ------------------------------------------------------------------ 3. venv
Step "3/9 创建虚拟环境"
$vpy = Join-Path $InstallDir ".venv\Scripts\python.exe"
if (-not (Test-Path $vpy)) {
    & $py[0] @($py[1..($py.Length - 1)]) -m venv (Join-Path $InstallDir ".venv")
    Ok ".venv 已创建"
} else {
    Ok ".venv 已存在，复用"
}

# ------------------------------------------------------------------ 4. 依赖
Step "4/9 安装依赖（首次约 1-3 分钟，会看到 pip 输出）"
try { & $vpy -m pip install --upgrade pip -q --disable-pip-version-check 2>&1 | Out-Null } catch { }
# 国内机器先走镜像，官方源放最后兜底
$mirrors = @(
    @('-i', 'https://pypi.tuna.tsinghua.edu.cn/simple'),
    @('-i', 'https://mirrors.aliyun.com/pypi/simple/'),
    @()
)
$installed = $false
foreach ($m in $mirrors) {
    try {
        & $vpy -m pip install -r (Join-Path $InstallDir "requirements.txt") -q @m
        if ($LASTEXITCODE -eq 0) {
            $installed = $true
            $label = if ($m.Length) { "（$($m[1])）" } else { "（官方源）" }
            Ok "依赖装好$label"
            break
        }
    } catch {
        Warn "这个源失败，换下一个"
    }
}
if (-not $installed) { Die "依赖装不上，先确认这台机器能上网/能连 pip 源" }
$nbver = (& $vpy -c "import nonebot;print(nonebot.__version__)" 2>$null)
if (-not $nbver) { Die "nonebot2 没装上，检查 requirements.txt" }
Ok "NoneBot2 $nbver"
Report "NoneBot2: $nbver"

# ------------------------------------------------------------------ 5. NapCat
if (-not $SkipNapCat) {
    Step "5/9 准备 NapCat 协议端"
    $napcat = Join-Path $InstallDir "napcat"
    if (Test-Path (Join-Path $napcat "napcat.mjs")) {
        Ok "NapCat 已存在，跳过"
    } else {
        New-Item -ItemType Directory -Force -Path $napcat | Out-Null
        $zip = Join-Path $env:TEMP "NapCat.Shell.zip"
        $sources = @()
        $local = Join-Path $InstallDir "NapCat.Shell.zip"
        if (Test-Path $local) { $sources += $local }
        $sources += "https://gitee.com/wangcc111/qq-bridge-dist/releases/download/v1.0/NapCat.Shell.zip"
        $sources += "https://ghproxy.net/https://github.com/NapNeko/NapCatQQ/releases/latest/download/NapCat.Shell.zip"
        $sources += "https://github.com/NapNeko/NapCatQQ/releases/latest/download/NapCat.Shell.zip"
        $done = $false
        foreach ($src in $sources) {
            try {
                if (Test-Path $src) {
                    Ok "用本地安装包"
                    Copy-Item $src $zip -Force
                } else {
                    Say "  下载：$src"
                    Invoke-WebRequest -Uri $src -OutFile $zip -UseBasicParsing -TimeoutSec 300
                }
                if ((Test-Path $zip) -and ((Get-Item $zip).Length -gt 5242880)) {
                    Expand-Archive -Path $zip -DestinationPath $napcat -Force
                    Remove-Item $zip -Force -ErrorAction SilentlyContinue
                    $done = $true
                    break
                }
                Warn "文件不完整，换下一个源"
            } catch { Warn "这个源失败，换下一个" }
        }
        if (-not $done) { Die "NapCat 全部源都失败：手动下 NapCat.Shell.zip 放到 $InstallDir 后重跑" }
        Ok "NapCat 就绪"
    }
    $silent = Join-Path $InstallDir "scripts\launcher-user-silent.bat"
    if ((Test-Path $silent) -and -not (Test-Path (Join-Path $napcat "launcher-user-silent.bat"))) {
        Copy-Item $silent (Join-Path $napcat "launcher-user-silent.bat") -Force
    }
} else {
    Step "5/9 跳过 NapCat（-SkipNapCat）"
}

# ------------------------------------------------------------------ 6. 工单 → 配置
Step "6/9 生成配置（ticket.yaml → config.yaml + personas）"
foreach ($d in @("data", "logs", "stickers", "tmp")) {
    if (-not (Test-Path (Join-Path $InstallDir $d))) { New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir $d) | Out-Null }
}
$userList = ($Users -split '[,\s]+' | Where-Object { $_ } | ForEach-Object { "    - `"$($_.Trim())`"" }) -join "`r`n"
$groupList = ($Groups -split '[,\s]+' | Where-Object { $_ } | ForEach-Object { "    - `"$($_.Trim())`"" }) -join "`r`n"

# 人格：给了 -PersonaPrompt 就整段塞进去（AI 起草的人格），否则用几个字段拼
$personaBlock = @"
  name: "$PersonaName"
  age: $PersonaAge
  who: "$PersonaWho"
  style: "$PersonaStyle"
  relation: "$PersonaRelation"
"@
if ($PersonaPrompt) {
    $indented = ($PersonaPrompt -split "`r?`n" | ForEach-Object { "    $_" }) -join "`r`n"
    $personaBlock = @"
  name: "$PersonaName"
  age: $PersonaAge
  prompt: |
$indented
"@
}

$dstTicket = Join-Path $InstallDir "ticket.yaml"
if ($TicketPath) {
    # AI / 操作手自己写好整份工单（含长人格 prompt）时走这条：原样用，不覆盖
    if (-not (Test-Path $TicketPath)) { Die "找不到工单 $TicketPath" }
    Copy-Item $TicketPath $dstTicket -Force
    Ok "使用已有工单：$TicketPath"
} else {
    $ticket = @"
# 由 remote-deploy.ps1 生成
robot:
  qq: "$Qq"

allow:
  users:
$userList
  groups:
$groupList

city: "$City"

api:
  base_url: "$BaseUrl"
  api_key: "$ApiKey"
  model: "$Model"

persona:
$personaBlock
"@
    Set-Content -Path $dstTicket -Value $ticket -Encoding UTF8
    Ok "已按参数生成 ticket.yaml"
}

$prevEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'   # 让 python 的 stderr 正常显示，再由 $LASTEXITCODE 判定
& $vpy (Join-Path $InstallDir "autoconfig.py") --ticket $dstTicket --config (Join-Path $InstallDir "config.yaml") --personas (Join-Path $InstallDir "data\personas.yaml")
$acRc = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($acRc -ne 0) { Die "autoconfig 失败（看上面的提示：api.base_url / api_key / model 必填）" }
Ok "config.yaml / data\personas.yaml 已生成"
Report "config.yaml: 已生成"

# 端口跟参数保持一致（老配置里默认也是 8199/8088）
& $vpy -c @"
import sys, yaml, pathlib
p = pathlib.Path(r'$InstallDir\config.yaml')
d = yaml.safe_load(p.read_text(encoding='utf-8')) or {}
d.setdefault('onebot11', {}).setdefault('reverse', {})['port'] = $Port
d.setdefault('http_api', {})['port'] = $ApiPort
if '$Qq': d['bot_qq'] = '$Qq'
p.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding='utf-8')
print('ports ok')
"@
if ($LASTEXITCODE -ne 0) { Die "写端口失败" }
Ok "端口：反向 WS $Port / 本机接口 $ApiPort"

# 用 -TicketPath 时命令行没给 Qq/Users，报告里从生成的配置回读，免得显示空白
if (-not $Qq -or -not $Users) {
    $readback = & $vpy -c @"
import yaml
d = yaml.safe_load(open(r'$InstallDir\config.yaml', encoding='utf-8')) or {}
w = ((d.get('autoreply') or {}).get('whitelist') or {})
print(str(d.get('bot_qq') or '') + '|' + ','.join(w.get('users') or []) + '|' + ','.join(w.get('groups') or []))
"@
    $parts = "$readback".Split('|')
    if (-not $Qq) { $Qq = $parts[0] }
    if (-not $Users) { $Users = $parts[1] }
    if ($parts.Length -gt 2 -and $parts[2]) { $Groups = $parts[2] }
}

# nb.env 由 main_nb.py 首次启动自动生成；这里先生成一份，方便 -NoStart 场景
& $vpy -c @"
import sys
sys.path.insert(0, r'$InstallDir')
from pathlib import Path
from qqbot.config import load_config
from main_nb import ensure_env_file
cfg = load_config(Path(r'$InstallDir\config.yaml'))
ensure_env_file(Path(r'$InstallDir\nb.env'), cfg)
print('nb.env ok')
"@
if ($LASTEXITCODE -ne 0) { Warn "nb.env 预生成失败（首启动时会再生成一次）" } else { Ok "nb.env 已就绪" }

# ------------------------------------------------------------------ 7. 桌面图标
Step "7/9 创建桌面快捷方式"
try {
    $lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) "QQ机器人.lnk"
    $ws = New-Object -ComObject WScript.Shell
    $sc = $ws.CreateShortcut($lnk)
    $sc.TargetPath = "$env:WINDIR\System32\wscript.exe"
    $sc.Arguments = '"' + (Join-Path $InstallDir "open_console.vbs") + '"'
    $sc.WorkingDirectory = $InstallDir
    $ico = Join-Path $InstallDir "assets\qq-bridge.ico"
    if (Test-Path $ico) { $sc.IconLocation = $ico }
    $sc.Save()
    Ok "桌面「QQ机器人」已就绪（双击 = 拉起服务并打开后台）"
} catch { Warn "快捷方式没建成：$_" }

# 两个网址也各做一个桌面图标：后台 + NapCat 面板
try {
    $desktop = [Environment]::GetFolderPath('Desktop')
    $ico = Join-Path $InstallDir "assets\qq-bridge.ico"
    $icoLine = if (Test-Path $ico) { "IconFile=$ico`r`nIconIndex=0`r`n" } else { "" }
    $urls = @(
        @{ Name = "机器人后台"; Url = "http://127.0.0.1:$ApiPort/admin" },
        @{ Name = "NapCat 面板"; Url = "http://127.0.0.1:6099" }
    )
    foreach ($u in $urls) {
        $f = Join-Path $desktop ($u.Name + ".url")
        $body = "[InternetShortcut]`r`nURL=$($u.Url)`r`n$icoLine"
        [System.IO.File]::WriteAllText($f, $body, [System.Text.Encoding]::Default)
        Ok "桌面「$($u.Name)」→ $($u.Url)"
    }
} catch { Warn "网址快捷方式没建成：$_" }

# ------------------------------------------------------------------ 8. 启动
Step "8/9 启动服务"
$started = $false
if (-not $NoStart) {
    $svc = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*main_nb.py*" -and $_.CommandLine -like "*$InstallDir*" }
    if ($svc) {
        Ok "服务已在跑（PID $($svc.ProcessId)）"
    } else {
        Start-Process -FilePath $vpy.Replace('python.exe', 'pythonw.exe') `
            -ArgumentList 'main_nb.py' -WorkingDirectory $InstallDir -WindowStyle Hidden
        Say "  已拉起 main_nb.py"
    }
    # 等 /status
    $deadline = (Get-Date).AddSeconds(120)
    $status = $null
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 3
        try {
            $status = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/status" -TimeoutSec 4
            if ($status) { break }
        } catch { }
    }
    if ($status) {
        $started = $true
        Ok "服务在线：connected=$($status.connected)  self_id=$($status.self_id)  处理器=$($status.plugins)"
        Report "服务: 在线（connected=$($status.connected), self_id=$($status.self_id), handlers=$($status.plugins)）"
    } else {
        Warn "120 秒内 /status 没起来，看日志：$InstallDir\logs\stderr.log / nonebot.log"
        Report "服务: 未就绪（需看日志）"
    }
} else {
    Warn "按 -NoStart 跳过启动"
}

# ------------------------------------------------------------------ 9. 报告
Step "9/9 远程验收报告"
$pyv = (& $vpy -c "import sys;print(sys.version.split()[0])")
Say "----------------------------------------------"
Say "安装目录 : $InstallDir"
Say "Python   : $pyv"
Say "框架     : NoneBot2 $nbver（nonebot-adapter-onebot）"
Say "机器人QQ : $(if ($Qq) { $Qq } else { '（还没登录，扫码后自动写入 config.yaml）' })"
Say "白名单   : $(if ($Users) { $Users } else { '（空 —— 待认领：tools\claim.py --auto）' })"
Say "端口     : 反向WS $Port / 本机接口 $ApiPort"
Say "服务     : $(if ($started) { '在线' } else { '未验证' })"
Say "----------------------------------------------"
Say ""
Say "----------------------------------------------"
Say "接下来（按顺序）：" Yellow
Say "  1) 手机 QQ 扫码登录机器人号（第一次必须扫码；已登录过会自动连上，跳过这步）"
Say "      需要扫码时执行：.venv\Scripts\python.exe login_qr.py"
Say "      Windows 防火墙放行 $ApiPort（本机）与 6099（NapCat 面板，扫完码可关）"
Say "  2) 认领白名单：让对方用自己要聊天的 QQ 给机器人发一句「在吗」"
Say "     （这时还不会回，正常）然后执行："
Say "      .venv\Scripts\python.exe tools\claim.py --auto"
Say "     它会自动把发消息的号加进白名单并热重载，再发一句就能聊"
Say ""
Say "验证（在机器人号上给机器人发消息）：" Cyan
Say "  发 /nb      → 应回复 NoneBot2 版本、连接数、处理器数量"
Say "  发 ping     → 应回复 pong"
Say "  发 help     → 应回复指令列表"
Say "  自检：.venv\Scripts\python.exe selfcheck.py   （要 12/12）"
Say ""
Say "日志：$InstallDir\logs\nonebot.log（框架侧）  qq-bridge.log（业务侧）" Gray
Say "手机端配置台：http://127.0.0.1:$ApiPort/admin" Gray
Say "==============================================" Cyan
$report | ForEach-Object { Say "  · $_" DarkGray }

#Requires -Version 5.1
<#
  qq-bridge 一键安装（Windows 10/11）
  用法：右键"使用 PowerShell 运行"，或双击同目录的 安装.bat
  做的事：建 Python 环境 → 装依赖 → 准备 NapCat → 生成配置和桌面图标
#>
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root

function Say($msg, $color = 'Gray') { Write-Host $msg -ForegroundColor $color }
function Step($n, $msg) { Write-Host "`n[$n] $msg" -ForegroundColor Cyan }

Say "==============================================" Cyan
Say "   qq-bridge 安装程序" Cyan
Say "==============================================" Cyan
Say "安装目录：$root"

# ---------------- 1. Python ----------------
Step 1 "检查 Python（需要 3.10 以上）"
$py = $null
foreach ($cand in @('py -3.12', 'py -3', 'python')) {
    try {
        $parts = $cand.Split(' ')
        $exe = $parts[0]
        $rest = @()
        if ($parts.Length -gt 1) { $rest += $parts[1..($parts.Length - 1)] }
        $ver = & $exe @rest -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $ver) {
            $maj, $min = $ver.Split('.')
            if ([int]$maj -eq 3 -and [int]$min -ge 10) { $py = @($exe) + $rest; Say "  找到 Python $ver（$cand）" Green; break }
        }
    } catch { }
}
if (-not $py) {
    Say "  没找到合适的 Python，尝试用 winget 自动安装…" Yellow
    try {
        winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
        $py = @('py', '-3.12')
        Say "  Python 3.12 已安装" Green
    } catch {
        Say "  自动安装失败。请手动安装 Python 3.12（勾选 Add to PATH）后重新运行本脚本。" Red
        Say "  下载：https://www.python.org/downloads/windows/" Red
        Read-Host "按回车退出"; exit 1
    }
}

# ---------------- 2. 虚拟环境 ----------------
Step 2 "创建虚拟环境 .venv"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & $py[0] @($py[1..($py.Length-1)]) -m venv .venv
    Say "  已创建" Green
} else {
    Say "  已存在，跳过" Green
}
$vpy = Join-Path $root ".venv\Scripts\python.exe"

# ---------------- 3. 依赖 ----------------
Step 3 "安装 Python 依赖（约 1-2 分钟）"
& $vpy -m pip install --upgrade pip -q
$ok = $false
try {
    & $vpy -m pip install -r requirements.txt -q
    $ok = $true
    Say "  依赖安装完成" Green
} catch {
    Say "  官方源失败，换清华镜像重试…" Yellow
    & $vpy -m pip install -r requirements.txt -q -i https://pypi.tuna.tsinghua.edu.cn/simple
    $ok = $true
    Say "  依赖安装完成（镜像）" Green
}
if (-not $ok) { Say "  依赖安装失败，检查网络后重试" Red; Read-Host "按回车退出"; exit 1 }

# ---------------- 4. NapCat ----------------
Step 4 "准备 NapCat（QQ 协议端，约 35MB）"
$napcat = Join-Path $root "napcat"
if (Test-Path (Join-Path $napcat "napcat.mjs")) {
    Say "  已存在，跳过下载" Green
} else {
    New-Item -ItemType Directory -Force -Path $napcat | Out-Null
    $zip = Join-Path $env:TEMP "NapCat.Shell.zip"

    $sources = @()
    # 优先用同目录自带的包（完全离线可用）
    $localPkg = Join-Path $root "NapCat.Shell.zip"
    if (Test-Path $localPkg) { $sources += $localPkg }
    # 其次 Gitee 发行版直链（国内直连、无需登录）
    $sources += "https://gitee.com/wangcc111/qq-bridge-dist/releases/download/v1.0/NapCat.Shell.zip"
    $sources += "https://gitee.com/wangcc111/qq-bridge-dist/raw/main/NapCat.Shell.zip"
    # 再试 GitHub 加速镜像
    $sources += "https://ghproxy.net/https://github.com/NapNeko/NapCatQQ/releases/latest/download/NapCat.Shell.zip"
    # 最后直连 GitHub
    $sources += "https://github.com/NapNeko/NapCatQQ/releases/latest/download/NapCat.Shell.zip"

    $done = $false
    foreach ($src in $sources) {
        try {
            if (Test-Path $src) {
                Say "  使用本地安装包" 
                Copy-Item $src $zip -Force
            } else {
                Say "  下载：$src"
                Invoke-WebRequest -Uri $src -OutFile $zip -UseBasicParsing -TimeoutSec 300
            }
            if ((Test-Path $zip) -and ((Get-Item $zip).Length -gt 5242880)) {
                Expand-Archive -Path $zip -DestinationPath $napcat -Force
                Remove-Item $zip -Force -ErrorAction SilentlyContinue
                Say "  NapCat 已就绪" Green
                $done = $true
                break
            }
            Say "  文件不完整，换下一个源" Yellow
        } catch {
            Say "  这个源失败，换下一个" Yellow
        }
    }
    if (-not $done) {
        Say "  全部源都失败了。手动办法：" Red
        Say "  1) 浏览器打开 https://gitee.com/wangcc111/qq-bridge-dist 下载 NapCat.Shell.zip" Red
        Say "  2) 放到安装目录根下，重新运行本脚本" Red
        Read-Host "按回车退出"; exit 1
    }
}

$silent = Join-Path $root "scripts\launcher-user-silent.bat"
if ((Test-Path $silent) -and -not (Test-Path (Join-Path $napcat "launcher-user-silent.bat"))) {
    Copy-Item $silent (Join-Path $napcat "launcher-user-silent.bat") -Force
    Say "  已放入静默启动脚本" Green
}

# ---------------- 5. 配置文件 ----------------
Step 5 "生成配置文件"
if (-not (Test-Path "config.yaml")) {
    Copy-Item "config.example.yaml" "config.yaml"
    Say "  已生成 config.yaml（稍后在任务单里填密钥）" Green
} else { Say "  config.yaml 已存在，保留不动" Green }
if (-not (Test-Path "data")) { New-Item -ItemType Directory -Force -Path "data" | Out-Null }
if (-not (Test-Path "data\personas.yaml")) {
    Copy-Item "personas.example.yaml" "data\personas.yaml"
    Say "  已生成 data\personas.yaml" Green
} else { Say "  data\personas.yaml 已存在，保留不动" Green }
foreach ($d in @("logs", "stickers")) { if (-not (Test-Path $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null } }

# ---------------- 6. Node（语音需要，可选） ----------------
Step 6 "检查 Node.js（语音功能需要，可选）"
try {
    $nodeVer = & node -v 2>$null
    if ($nodeVer) { Say "  已安装 Node $nodeVer" Green } else { throw "no node" }
} catch {
    Say "  没装 Node.js，语音会退回文字（不影响聊天）" Yellow
    Say "  需要语音再装：https://nodejs.org/" Yellow
}

# ---------------- 7. 桌面图标 ----------------
Step 7 "创建桌面图标"
try {
    $desktop = [Environment]::GetFolderPath('Desktop')
    $lnk = Join-Path $desktop "QQ机器人.lnk"
    $ws = New-Object -ComObject WScript.Shell
    $sc = $ws.CreateShortcut($lnk)
    $sc.TargetPath = "$env:WINDIR\System32\wscript.exe"
    $sc.Arguments = '"' + (Join-Path $root "open_console.vbs") + '"'
    $sc.WorkingDirectory = $root
    $ico = Join-Path $root "assets\qq-bridge.ico"
    if (Test-Path $ico) { $sc.IconLocation = $ico }
    $sc.Save()
    Say "  桌面已生成「QQ机器人」（双击 = 拉起服务并打开后台）" Green
} catch { Say "  创建快捷方式失败：$_" Yellow }

# 两个网址也各做一个桌面图标：后台 + NapCat 面板
try {
    $desktop = [Environment]::GetFolderPath('Desktop')
    $ico = Join-Path $root "assets\qq-bridge.ico"
    $icoLine = if (Test-Path $ico) { "IconFile=$ico`r`nIconIndex=0`r`n" } else { "" }
    foreach ($u in @(@{n="机器人后台"; u="http://127.0.0.1:8088/admin"}, @{n="NapCat 面板"; u="http://127.0.0.1:6099"})) {
        $f = Join-Path $desktop ($u.n + ".url")
        [System.IO.File]::WriteAllText($f, "[InternetShortcut]`r`nURL=$($u.u)`r`n$icoLine", [System.Text.Encoding]::Default)
        Say "  桌面已生成「$($u.n)」→ $($u.u)" Green
    }
} catch { Say "  网址快捷方式失败：$_" Yellow }

# ---------------- 8. 完成 ----------------
Step 8 "安装完成"
Say ""
Say "接下来：打开本目录的 任务单.md，把客户信息填在【① 填写区】，" Green
Say "交给 AI 执行，或手动运行：.venv\Scripts\python.exe autoconfig.py --ticket ticket.yaml" Green
Say "以后双击桌面「QQ机器人」就能启动 / 扫码 / 备份。" Gray

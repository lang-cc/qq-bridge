#Requires -Version 5.1
<#
  qq-bridge 更新脚本
  从仓库拉最新代码覆盖本地，保留 config.yaml / nb.env / data / napcat / stickers / .venv / logs
  用法：双击上一层的「更新.bat」，或
        powershell -ExecutionPolicy Bypass -File scripts\update.ps1
#>
$ErrorActionPreference = 'Stop'

# 仓库位置（Gitee，owner/name）与分支
$Repo   = "wangcc111/qq-bridge"
$Branch = "main"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Definition)
Set-Location $root

function Say($m, $c = 'Gray') { Write-Host $m -ForegroundColor $c }

# 绝不覆盖/删除的条目：配置、密钥、记忆、协议端、表情包、虚拟环境、日志、临时
$keep = @('config.yaml', 'nb.env', 'data', 'logs', 'napcat', 'stickers',
          '.venv', '.venv-tts', '.venv-*', 'tmp', 'dist', 'backups', '.git', '.cache',
          'tools\ffmpeg', 'tools\dl', 'tools\silk\node_modules', '__pycache__')

Say "==============================================" Cyan
Say "   qq-bridge 更新" Cyan
Say "==============================================" Cyan
Say "仓库：$Repo（$Branch）"
Say "目录：$root"

# ---------------- 1. 下载 ----------------
Say "`n[1/4] 下载最新代码" Cyan
$zip = Join-Path $env:TEMP "qq-bridge-update.zip"
Remove-Item $zip -Force -ErrorAction SilentlyContinue

$src = "https://gitee.com/$Repo/repository/archive/$Branch.zip"

$got = $false
for ($i = 1; $i -le 3; $i++) {
    try {
        Say "  下载（第 $i 次）：$src"
        Invoke-WebRequest -Uri $src -OutFile $zip -UseBasicParsing -TimeoutSec 300
        if ((Test-Path $zip) -and ((Get-Item $zip).Length -gt 1048576)) { $got = $true; break }
        Say "  包不完整，重试" Yellow
    } catch {
        if ("$_" -match '403') {
            Say "  403：仓库是私有的，匿名下载被拒。" Red
            Say "  解决：Gitee 仓库设置里改成公开，或手动下载 ZIP 解压覆盖代码。" Red
            break
        }
        Say "  这次失败，重试" Yellow
    }
}
if (-not $got) {
    Say "`n所有源都失败：检查网络，或手动去仓库 Download ZIP 后解压覆盖代码。" Red
    Read-Host "按回车退出"; exit 1
}
Say "  下载完成（$([math]::Round((Get-Item $zip).Length / 1MB, 1)) MB）" Green

# ---------------- 2. 备份现有代码 ----------------
Say "`n[2/4] 备份现有代码" Cyan
$bkDir = Join-Path $root "backups"
if (-not (Test-Path $bkDir)) { New-Item -ItemType Directory -Force -Path $bkDir | Out-Null }
$bk = Join-Path $bkDir ("code-before-update-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".zip")
try {
    $items = @('qqbot', 'nb', 'static', 'assets', 'tools', 'docs') | Where-Object { Test-Path (Join-Path $root $_) }
    $items += Get-ChildItem $root -File -Include *.py, *.ps1, *.bat, *.vbs, *.md, *.yaml, *.txt | ForEach-Object { $_.Name }
    Compress-Archive -Path ($items | ForEach-Object { Join-Path $root $_ }) -DestinationPath $bk -Force
    Say "  已备份：$bk" Green
} catch {
    Say "  备份失败（继续更新）：$_" Yellow
}

# ---------------- 3. 覆盖代码 ----------------
Say "`n[3/4] 覆盖代码（保留配置和记忆）" Cyan
$work = Join-Path $env:TEMP ("qq-bridge-x-" + [guid]::NewGuid().ToString('N'))
Expand-Archive -Path $zip -DestinationPath $work -Force
$src = Get-ChildItem $work -Directory | Select-Object -First 1
if (-not $src) { Say "解压结果异常" Red; Read-Host "按回车退出"; exit 1 }

$copied = 0
foreach ($item in Get-ChildItem $src.FullName) {
    $name = $item.Name
    if ($keep -contains $name) { continue }
    if ($name -eq '.git' -or $name -like '.venv*') { continue }
    try {
        if ($item.PSIsContainer) {
            if ($name -eq 'tools') {
                # tools 里只更新脚本，跳过 node_modules / ffmpeg / dl
                Get-ChildItem $item.FullName -File | ForEach-Object {
                    Copy-Item $_.FullName (Join-Path $root "tools\$($_.Name)") -Force
                }
                $silkSrc = Join-Path $item.FullName 'silk'
                if (Test-Path $silkSrc) {
                    New-Item -ItemType Directory -Force -Path (Join-Path $root 'tools\silk') | Out-Null
                    Get-ChildItem $silkSrc -File | ForEach-Object {
                        Copy-Item $_.FullName (Join-Path $root "tools\silk\$($_.Name)") -Force
                    }
                }
            } else {
                Copy-Item $item.FullName (Join-Path $root $name) -Recurse -Force
            }
        } else {
            Copy-Item $item.FullName (Join-Path $root $name) -Force
        }
        $copied++
    } catch {
        Say "  跳过 $name：$_" Yellow
    }
}
Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $zip -Force -ErrorAction SilentlyContinue
Say "  已更新 $copied 项" Green

# ---------------- 4. 自检 ----------------
Say "`n[4/4] 更新后自检" Cyan
$py = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $py) {
    try {
        $env:PYTHONIOENCODING = 'utf-8'
        & $py (Join-Path $root "selfcheck.py")
    } catch {
        Say "  自检没跑起来：$_" Yellow
    }
} else {
    Say "  没找到 .venv，跳过自检" Yellow
}

Say "`n代码已更新。如果服务正在运行，重启一次才会生效：" Cyan
Say "  双击桌面「QQ机器人」→ 后台概览页点「重启」" Cyan
Read-Host "`n按回车关闭"
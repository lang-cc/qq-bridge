#Requires -Version 5.1
<#
  qq-bridge 更新脚本（更新渠道 = GitHub 公开仓库）

  做三件事：拉最新代码覆盖本地 → 备份旧代码 → 自检。配置文件、密钥、记忆、
  协议端、表情包、虚拟环境、日志一律不动，所以更新完机器人还是原来那个号、原来那些记忆。

  用法：
    双击上一层的「更新.bat」
    powershell -ExecutionPolicy Bypass -File scripts\update.ps1
    powershell -ExecutionPolicy Bypass -File scripts\update.ps1 -NoPause    # 远程/无人值守，末尾不等待回车

  回滚：把 backups\code-before-update-<时间>.zip 解压回安装目录即可。
#>

[CmdletBinding()]
param(
    [string]$Branch = "main",
    [switch]$NoPause                      # 不 Read-Host 等待回车（远程代跑时用）
)

$ErrorActionPreference = 'Stop'

# ---- 更新源：GitHub（公开仓库，匿名可下载，不用登录、不会 403）----
$Owner  = "lang-cc"
$Repo   = "qq-bridge"
$Slug   = "$Owner/$Repo"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Definition)
Set-Location $root

# Win10 老机器上 PowerShell 5.1 默认还在用 TLS1.0，连 GitHub 会直接握手失败
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }

function Say($m, $c = 'Gray') { Write-Host $m -ForegroundColor $c }
function Bye($code = 1) {
    if (-not $NoPause) { Read-Host "`n按回车关闭" | Out-Null }
    exit $code
}

# 当前版本（读 VERSION.txt / .git，读不出来就显示 -）
function Get-Ver {
    $py = Join-Path $root ".venv\Scripts\python.exe"
    if (-not (Test-Path $py)) { return "-" }
    # 路径用正斜杠传给 Python：反斜杠会被当成转义，Python 3.12 会往 stderr 打警告
    $here = $root -replace '\\', '/'
    $code = "import sys;sys.path.insert(0,'$here');from qqbot import version;print(version.info()['label'])"
    $pref = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'      # python / curl 的警告走 stderr，Stop 会把它当致命错误
    try {
        $env:PYTHONIOENCODING = 'utf-8'
        $out = & $py -c $code 2>$null
    } catch {
        $out = $null
    } finally {
        $ErrorActionPreference = $pref
    }
    if ($out) { return ($out | Select-Object -Last 1).ToString().Trim() }
    return "-"
}

# 绝不覆盖/删除的条目：配置、密钥、记忆、协议端、表情包、虚拟环境、日志、临时
$keep = @('config.yaml', 'nb.env', 'data', 'logs', 'napcat', 'stickers',
          '.venv', '.venv-tts', '.venv-*', 'tmp', 'dist', 'backups', '.git', '.cache')

Say "==============================================" Cyan
Say "   qq-bridge 更新" Cyan
Say "==============================================" Cyan
Say "更新源：GitHub $Slug（$Branch）"
Say "目录　：$root"
$before = Get-Ver
Say "当前版本：$before"
Say ""

# ---------------- 1. 下载 ----------------
Say "[1/5] 下载最新代码" Cyan
$zip = Join-Path $env:TEMP "qq-bridge-update.zip"
Remove-Item $zip -Force -ErrorAction SilentlyContinue

# 五个源内容相同，前一个不通/太慢就换下一个：官方 → 国内加速 → Gitee 备用（可能私有/403）
$sources = @(
    "https://codeload.github.com/$Slug/zip/refs/heads/$Branch",
    "https://gh-proxy.com/https://github.com/$Slug/archive/refs/heads/$Branch.zip",
    "https://ghproxy.net/https://github.com/$Slug/archive/refs/heads/$Branch.zip",
    "https://github.com/$Slug/archive/refs/heads/$Branch.zip",
    "https://gitee.com/wangcc111/qq-bridge/repository/archive/$Branch.zip"
)

# 用 curl.exe 下（Win10 1803 起自带）：PS5.1 的 Invoke-WebRequest 下大文件容易卡死；
# curl 还能设「比 300KB/s 还慢超过 12 秒就放弃换源」——国内直连 GitHub 常常就是这速度
function Get-Pkg($url, $out) {
    Remove-Item $out -Force -ErrorAction SilentlyContinue
    $curl = (Get-Command curl.exe -ErrorAction SilentlyContinue).Source
    $pref = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'      # curl 的错误/警告走 stderr，Stop 会把它当致命错误
    try {
        if ($curl) {
            & $curl -sS -L --fail --connect-timeout 15 `
                --speed-limit 307200 --speed-time 12 --max-time 1800 -o $out $url 2>$null
            $code = $LASTEXITCODE
        } else {
            Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing -TimeoutSec 600
            $code = 0
        }
    } catch {
        Say "  $($_.Exception.Message)" DarkGray
        $code = 1
    } finally {
        $ErrorActionPreference = $pref
    }
    if ($code -ne 0) { Say "  这个源没下来（退出码 $code）" DarkGray; return $false }
    return (Test-Path $out)
}

$got = $false
foreach ($src in $sources) {
    Say "  下载：$src"
    if (-not (Get-Pkg $src $zip)) { Say "  换下一个源" Yellow; continue }
    if ((Get-Item $zip).Length -gt 1048576) { $got = $true; break }
    Say "  包太小，不像完整代码，换下一个" Yellow
}
if (-not $got) {
    Say "`n所有源都失败：检查网络（能不能打开 github.com），或让对方把 zip 解压覆盖到安装目录：" Red
    Say "  https://github.com/$Slug/archive/refs/heads/$Branch.zip" Red
    Bye 1
}
Say "  下载完成（$([math]::Round((Get-Item $zip).Length / 1MB, 1)) MB）" Green

# 先解压到临时目录并校验：确认是完整代码包再动本地
$work = Join-Path $env:TEMP ("qq-bridge-x-" + [guid]::NewGuid().ToString('N'))
Expand-Archive -Path $zip -DestinationPath $work -Force
$src = Get-ChildItem $work -Directory | Select-Object -First 1
if (-not $src -or -not (Test-Path (Join-Path $src.FullName "qqbot\__init__.py"))) {
    Say "`n下载到的包内容不对（没有 qqbot/），已放弃更新，本地一个文件都没动。" Red
    Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $zip -Force -ErrorAction SilentlyContinue
    Bye 1
}

# ---------------- 2. 备份现有代码 ----------------
Say "`n[2/5] 备份现有代码" Cyan
$bkDir = Join-Path $root "backups"
if (-not (Test-Path $bkDir)) { New-Item -ItemType Directory -Force -Path $bkDir | Out-Null }
$bk = Join-Path $bkDir ("code-before-update-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".zip")
try {
    $items = @('qqbot', 'nb', 'static', 'assets', 'tools', 'docs', 'scripts') | Where-Object { Test-Path (Join-Path $root $_) }
    $items += Get-ChildItem $root -File | Where-Object { $_.Extension -in '.py', '.ps1', '.bat', '.vbs', '.md', '.yaml', '.txt' } | ForEach-Object { $_.Name }
    Compress-Archive -Path ($items | ForEach-Object { Join-Path $root $_ }) -DestinationPath $bk -Force
    Say "  已备份：$bk" Green
} catch {
    Say "  备份失败（继续更新）：$($_.Exception.Message)" Yellow
}

# ---------------- 3. 覆盖代码 ----------------
Say "`n[3/5] 覆盖代码（保留配置和记忆）" Cyan
$copied = 0
$pref = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
foreach ($item in Get-ChildItem $src.FullName) {
    $name = $item.Name
    if ($keep -contains $name) { continue }
    if ($name -eq '.git' -or $name -like '.venv*') { continue }
    if ($item.PSIsContainer) {
        $dst = Join-Path $root $name
        if (-not (Test-Path $dst)) { New-Item -ItemType Directory -Force -Path $dst | Out-Null }
        # 目录必须「合并内容」，不能用 Copy-Item -Recurse（那会在里面再套一层 名字\名字）
        $opt = @('/E', '/NFL', '/NDL', '/NJH', '/NJS', '/NP', '/R:1', '/W:1')
        if ($name -eq 'scripts') { $opt += @('/XF', 'update.ps1') }   # 自己正在跑，下面单独处理
        & robocopy $item.FullName $dst @opt | Out-Null
        if ($LASTEXITCODE -ge 8) { Say "  $name 里有文件没复制成功（robocopy $LASTEXITCODE）" Yellow }
        $copied++
    } else {
        try {
            Copy-Item $item.FullName (Join-Path $root $name) -Force
            $copied++
        } catch {
            Say "  跳过 $name：$($_.Exception.Message)" Yellow
        }
    }
}
$ErrorActionPreference = $pref

# 更新脚本自己正在运行，Windows 不让覆盖它：先存成 .new，下次双击「更新.bat」时由它换上去
# 比较时忽略换行差异（GitHub 打的包是 LF，本机可能是 CRLF），否则每次都会白写一个 .new
function Test-SameScript($a, $b) {
    try {
        $ta = (Get-Content $a -Raw -Encoding UTF8) -replace "`r`n", "`n"
        $tb = (Get-Content $b -Raw -Encoding UTF8) -replace "`r`n", "`n"
        return ($ta -ceq $tb)
    } catch {
        return $false
    }
}
try {
    $newSelf = Join-Path $src.FullName 'scripts\update.ps1'
    $curSelf = Join-Path $root 'scripts\update.ps1'
    if ((Test-Path $newSelf) -and (Test-Path $curSelf)) {
        if (-not (Test-SameScript $newSelf $curSelf)) {
            Copy-Item $newSelf (Join-Path $root 'scripts\update.ps1.new') -Force
            Say "  更新脚本本身也有新版本：已存为 scripts\update.ps1.new，下次双击「更新.bat」自动换上" Yellow
        }
    }
} catch {
    Say "  更新脚本自身没换成（不影响这次更新）：$($_.Exception.Message)" Yellow
}

# GitHub 打的 zip 里 .bat / .ps1 / .vbs 是 LF。Windows 老版本 cmd / WSH 对 LF 的 .bat 容易出怪问题，
# 这里按字节补 CR（不动编码，也不碰 BOM），已经是对的就不写。
function Repair-Crlf($path) {
    try {
        $bytes = [System.IO.File]::ReadAllBytes($path)
        $need = $false
        for ($i = 0; $i -lt $bytes.Length; $i++) {
            if ($bytes[$i] -eq 10 -and ($i -eq 0 -or $bytes[$i - 1] -ne 13)) { $need = $true; break }
        }
        if (-not $need) { return $false }
        $ms = New-Object System.IO.MemoryStream
        for ($i = 0; $i -lt $bytes.Length; $i++) {
            if ($bytes[$i] -eq 10 -and ($i -eq 0 -or $bytes[$i - 1] -ne 13)) { $ms.WriteByte(13) }
            $ms.WriteByte($bytes[$i])
        }
        [System.IO.File]::WriteAllBytes($path, $ms.ToArray())
        return $true
    } catch {
        return $false
    }
}
$crlf = 0
foreach ($ext in @('*.bat', '*.ps1', '*.vbs')) {
    Get-ChildItem -Path $root -Filter $ext -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch '\\(data|logs|backups|napcat|tmp|dist|\.venv[^\\]*)\\' } |
        ForEach-Object { if (Repair-Crlf $_.FullName) { $crlf++ } }
}
if ($crlf -gt 0) { Say "  已把 $crlf 个 .bat/.ps1/.vbs 的换行统一成 Windows 格式" DarkGray }


Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $zip -Force -ErrorAction SilentlyContinue
Say "  已更新 $copied 项" Green

# ---------------- 4. 写版本标记 ----------------
# 客户的机器上没有 .git，控制台顶栏的版本号就靠这个文件；更新完一看时间/提交号变了就说明生效了
Say "`n[4/5] 写版本标记" Cyan
$ver = ""
try {
    $initTxt = Get-Content (Join-Path $root "qqbot\__init__.py") -Raw -Encoding UTF8
    $m = [regex]::Match($initTxt, '__version__\s*=\s*[''"]{1}([^''"]+)')
    if ($m.Success) { $ver = $m.Groups[1].Value }
} catch { }

$commit = ""
try {
    # 顺手问一下 GitHub 最新提交号（拿不到就算了，不影响更新）
    $api = Invoke-RestMethod -Uri "https://api.github.com/repos/$Slug/commits/$Branch" `
        -Headers @{ 'User-Agent' = 'qq-bridge-updater' } -TimeoutSec 15
    if ($api.sha) { $commit = $api.sha.Substring(0, 7) }
} catch { }

$stamp = @(
    "# qq-bridge 更新标记（scripts/update.ps1 自动写入，删掉也不影响运行）",
    "version=$ver",
    "ref=$Branch",
    "commit=$commit",
    "source=github $Slug",
    ("updated_at=" + (Get-Date -Format "MM-dd HH:mm"))
) -join "`r`n"
try {
    Set-Content -Path (Join-Path $root "VERSION.txt") -Value $stamp -Encoding UTF8
    if ($commit) { Say "  已写入 VERSION.txt（v$ver @$commit）" Green }
    else { Say "  已写入 VERSION.txt（v$ver）" Green }
} catch {
    Say "  写 VERSION.txt 失败（不影响运行）：$($_.Exception.Message)" Yellow
}

# ---------------- 5. 自检 ----------------
Say "`n[5/5] 更新后自检" Cyan
$py = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $py) {
    try {
        $env:PYTHONIOENCODING = 'utf-8'
        & $py (Join-Path $root "selfcheck.py")
    } catch {
        Say "  自检没跑起来：$($_.Exception.Message)" Yellow
    }
} else {
    Say "  没找到 .venv，跳过自检" Yellow
}

$after = Get-Ver
Say "`n更新完成：" Gray
Say "  更新前 $before" Gray
Say "  更新后 $after" Green
Say "`n如果服务正在运行，重启一次才会用上新代码：" Cyan
Say "  双击桌面「QQ机器人」→ 后台概览页点「重启」" Cyan
Say "  回滚：把 $bk 解压回 $root" DarkGray
Bye 0

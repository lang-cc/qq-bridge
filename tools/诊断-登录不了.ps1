# 登录不了 · 一键体检（在客户机器上，用「管理员」PowerShell 跑）
# 用法：powershell -NoProfile -ExecutionPolicy Bypass -File .\诊断-登录不了.ps1
param([string]$Root = 'D:\qqbridge')

$ErrorActionPreference = 'SilentlyContinue'
function H($t){ Write-Host "`n===== $t =====" -ForegroundColor Cyan }

H '1. 这台机器'
Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
(Get-CimInstance Win32_OperatingSystem).Caption
"安装目录：$Root  存在=$(Test-Path $Root)"

H '2. 关键进程（QQ 不在 = 没人扫码 / 被关掉了）'
Get-Process QQ, QQProtect, node, python -ErrorAction SilentlyContinue |
    Select-Object Name, Id, StartTime | Format-Table -AutoSize | Out-String -Width 120

H '3. 端口（后台 8088 / OneBot 3000 / 面板 6099 或 5099）'
foreach ($p in 8088, 3000, 6099, 5099, 8199) {
    $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    if ($c) { "  {0,-5} 在听   PID={1}" -f $p, $c[0].OwningProcess }
    else    { "  {0,-5} 没听" -f $p }
}

H '4. 机器人服务自述状态（看 connected）'
$r = curl.exe -s -m 5 http://127.0.0.1:8088/status
if ($r) { $r } else { '  8088 无响应 → 机器人主服务没起来' }

H '5. 日志尾部'
foreach ($f in 'logs\boot.log', 'logs\watchdog.log', 'logs\napcat.log', 'logs\snowluma.log') {
    $p = Join-Path $Root $f
    if (Test-Path $p) {
        "--- $f ---"
        Get-Content $p -Tail 12
    }
}

H '6. 自启动'
Get-CimInstance Win32_StartupCommand | Select-Object Name, Command |
    Format-Table -AutoSize | Out-String -Width 120

Write-Host "`n把上面整段输出发我，就知道是哪一种登录不了。" -ForegroundColor Green

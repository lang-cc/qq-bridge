#Requires -Version 5.1
<#
  一条命令的远程代装入口（只是把参数转给 scripts\remote-deploy.ps1）

  例：
    powershell -ExecutionPolicy Bypass -File deploy.ps1 -ZipPath D:\qq-bridge-full.zip `
        -Qq 10001 -Users 20002 -BaseUrl https://api.deepseek.com/v1 `
        -ApiKey sk-xxx -Model deepseek-chat -PersonaName 小柚

  参数说明见 scripts\remote-deploy.ps1 顶部注释。
#>
$ErrorActionPreference = 'Stop'
$here = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Definition }
$child = Join-Path $here "scripts\remote-deploy.ps1"
if (-not (Test-Path $child)) {
    Write-Host "找不到 scripts\remote-deploy.ps1，请确认整个目录都解压出来了" -ForegroundColor Red
    exit 1
}
& $child @args
exit $LASTEXITCODE

@echo off
chcp 65001 >nul
rem SnowLuma 前台启动（有窗口，方便看临时密码 / 注入日志）
rem 正常使用不用双击这个：boot.py / watchdog.py 会按 config.yaml 的 protocol_backend 自动拉起
cd /d "%~dp0"
if exist node.exe (
  "%~dp0node.exe" index.mjs
) else (
  node index.mjs
)
pause

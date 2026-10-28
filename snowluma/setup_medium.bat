@echo off
rem 以「当前用户/有限权限」(Medium 完整性) 把 SnowLuma 部署到 E:\snowluma 并启动。
rem 放在 E:\dsqq 里不行：那是 DSH 工作区，整棵树带 Low 完整性标签，node 会被封顶成
rem Low，注入不了 Medium 的 QQ（面板报「Node 完整性过低」）。
setlocal
set SL=E:\snowluma
set SRC=E:\dsqq\snowluma

if not exist "%SL%" mkdir "%SL%"
cd /d "%SL%"

rem 解包（bsdtar 能直接处理 zip）
tar -xf "%SRC%\SnowLuma-v2.2.1-win-x64.zip" -C "%SL%"

rem 配置 + 启动脚本
if not exist "%SL%\config" mkdir "%SL%\config"
copy /Y "%SRC%\config\onebot.json" "%SL%\config\onebot.json" >nul
copy /Y "%SRC%\config\runtime.json" "%SL%\config\runtime.json" >nul
copy /Y "%SRC%\run_hidden.bat" "%SL%\run_hidden.bat" >nul
if exist "%SRC%\config\onebot_*.json" copy /Y "%SRC%\config\onebot_*.json" "%SL%\config\" >nul

echo done > "%SL%\deploy-ok.txt"
endlocal

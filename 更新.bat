@echo off
rem qq-bridge updater: pull latest code from the repo, keep config/data/napcat/stickers (ASCII only)
cd /d "%~dp0"

rem update.ps1 cannot overwrite itself while running: the previous run left a newer copy as .new
if exist "%~dp0scripts\update.ps1.new" (
    move /y "%~dp0scripts\update.ps1.new" "%~dp0scripts\update.ps1" >nul 2>&1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\update.ps1"

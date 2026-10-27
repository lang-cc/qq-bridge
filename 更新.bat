@echo off
rem qq-bridge updater: pull latest code from the repo, keep config/data/napcat/stickers (ASCII only)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\update.ps1"
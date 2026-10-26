@echo off
rem start qq-bridge service + NapCat (visible windows, for manual debug)
cd /d %~dp0
start "qq-bridge" cmd /c ".venv\Scripts\python.exe main.py"
timeout /t 3 >nul
start "NapCat" /d "%~dp0napcat" cmd /c "launcher-user.bat -q 1126449714"
echo qq-bridge: http://127.0.0.1:8088   ws: ws://127.0.0.1:8199/onebot/v11/ws

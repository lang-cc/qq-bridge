@echo off
rem stop qq-bridge service and NapCat/QQ  (ASCII only: cmd codepage safety)
taskkill /f /im QQ.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8088" ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8199" ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
echo stopped.

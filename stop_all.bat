@echo off
rem stop qq-bridge service and protocol side (NapCat / SnowLuma) + QQ  (ASCII only)
taskkill /f /im QQ.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8088" ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8199" ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
rem NapCat webui 6099 / SnowLuma webui 5099
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":6099" ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5099" ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
echo stopped.

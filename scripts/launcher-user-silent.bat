@echo off
rem silent launcher: same as launcher-user.bat but without pause (ASCII only)
setlocal DisableDelayedExpansion
cd /d "%~dp0" || exit /b 1
set "NAPCAT_PATCH_PACKAGE=%cd%\qqnt.json"
set "NAPCAT_LOAD_PATH=%cd%\loadNapCat.js"
set "NAPCAT_INJECT_PATH=%cd%\NapCatWinBootHook.dll"
set "NAPCAT_LAUNCHER_PATH=%cd%\NapCatWinBootMain.exe"
set "NAPCAT_MAIN_PATH=%cd%\napcat.mjs"
set "RetString="
for /f "tokens=2*" %%a in ('reg query "HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\QQ" /v "UninstallString"') do (
    set "RetString=%%~b"
    goto :napcat_boot
)
echo QQ installation was not found in the registry.
exit /b 1

:napcat_boot
for %%a in ("%RetString%") do (
    set "pathWithoutUninstall=%%~dpa"
)
set "QQPath=%pathWithoutUninstall%QQ.exe"
if not exist "%QQPath%" (
    echo provided QQ path is invalid
    exit /b 1
)
"%NAPCAT_LAUNCHER_PATH%" "%QQPath%" "%NAPCAT_INJECT_PATH%" %*
exit /b %ERRORLEVEL%

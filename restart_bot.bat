@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo        StartupBot Restart Utility
echo ========================================

echo.
echo [1/2] Stopping existing bot processes...

:: 1. Try to kill the CMD window with the specific title
taskkill /F /FI "WINDOWTITLE eq Discord Bot - StartupBot*" /T >nul 2>&1

:: 2. Try to kill any python process running startupbot.py specifically
:: This is more precise than killing all python.exe instances
powershell -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*startupbot.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

echo Done.

echo.
echo [2/2] Starting StartupBot...
:: Start the bot in a new window using the existing start_bot.bat
start "" "start_background_bot.bat

echo.
echo Bot restart command issued.
echo You can close this window.
timeout /t 3
exit

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


echo Done.

echo.
echo [2/2] Starting StartupBot...
:: Start the bot in a new window using the existing start_bot.bat
start "" "start_bot.bat"



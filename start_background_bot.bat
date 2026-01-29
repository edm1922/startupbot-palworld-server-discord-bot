@echo off
cd /d "%~dp0"
set "SCRIPT_PATH=main.py"
echo Starting Bot in Background (Windowless)...
:: We use start "" (without /b) to ensure the bot continues running even after this window is closed.
start "" pythonw.exe "%SCRIPT_PATH%"
echo.
echo Bot has been launched in the background.
echo You can check 'logs/bot_background.log' for activity or errors.
echo.
echo To stop the bot, use Task Manager to end 'pythonw.exe' 
echo or use: taskkill /F /IM pythonw.exe
echo.
timeout /t 3
exit

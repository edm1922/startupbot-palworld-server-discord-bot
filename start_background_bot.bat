@echo off
cd /d "%~dp0"
set "SCRIPT_PATH=startupbot.py"
echo Starting Bot in Background (Windowless)...
start /b pythonw.exe "%SCRIPT_PATH%"
echo Bot has been launched in the background.
echo To stop it, use Task Manager to end 'pythonw.exe' or use 'taskkill /F /IM pythonw.exe'.
pause

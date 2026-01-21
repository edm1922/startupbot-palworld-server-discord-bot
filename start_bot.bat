@echo off
cd /d "%~dp0"
title Discord Bot - StartupBot
echo Starting StartupBot...
:loop
python startupbot.py
echo.
echo Bot crashed or stopped. Restarting in 5 seconds...
timeout /t 5
goto loop

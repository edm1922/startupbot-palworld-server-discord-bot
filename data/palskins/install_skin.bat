@echo off
setlocal enabledelayedexpansion

:: The target relative path
set "REL_PATH=Pal\Content\Paks"
set "STEAM_PATH=steamapps\common\Palworld"
set "FULL_REL_PATH=%STEAM_PATH%\%REL_PATH%"

set "FOUND_PATH="

echo ======================================================
echo          PALWORLD SKIN AUTO-INSTALLER
echo ======================================================
echo.
echo 🔍 Searching for Palworld installation...

:: 1. Check most common Steam library locations first
set "SEARCH_DIRS="
set "SEARCH_DIRS=!SEARCH_DIRS! "C:\Program Files (x86)\Steam""
set "SEARCH_DIRS=!SEARCH_DIRS! "C:\Program Files\Steam""

for %%D in (C D E F G H I J K L M N O P Q R S T U V W X Y Z) do (
    set "SEARCH_DIRS=!SEARCH_DIRS! "%%D:\SteamLibrary""
    set "SEARCH_DIRS=!SEARCH_DIRS! "%%D:\Steam""
    set "SEARCH_DIRS=!SEARCH_DIRS! "%%D:\""
)

:: Loop through potential root directories
for %%S in (%SEARCH_DIRS%) do (
    if exist "%%~S\%FULL_REL_PATH%" (
        set "FOUND_PATH=%%~S\%FULL_REL_PATH%"
        goto :FOUND
    )
)

:NOT_FOUND
echo.
echo ❌ ERROR: Could not find Palworld path automatically.
echo.
echo Please ensure Palworld is installed via Steam.
echo If you use a custom path, please move this file and the skin
echo into your "Palworld\Pal\Content\Paks" folder manually.
echo.
pause
exit /b

:FOUND
echo.
echo ✅ Found Path: %FOUND_PATH%
set "MODS_FOLDER=%FOUND_PATH%\~mods"

if not exist "%MODS_FOLDER%" (
    echo 📁 Creating ~mods folder...
    mkdir "%MODS_FOLDER%"
)

echo.
echo 🚚 Installing skins...
set "COUNT=0"
for %%F in (*.pak) do (
    echo Installing: %%F
    move /y "%%F" "%MODS_FOLDER%\"
    set /a COUNT+=1
)

if %COUNT% EQU 0 (
    echo ⚠️ No .pak files found in this folder to install.
) else (
    echo.
    echo ✨ %COUNT% Skin(s) installed successfully! 
    echo 🎮 You can now start Palworld.
)

echo.
pause

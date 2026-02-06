@echo off
setlocal enabledelayedexpansion

:: The target relative path
set "REL_PATH=Pal\Content\Paks"
set "STEAM_PATH=steamapps\common\Palworld"
set "FULL_REL_PATH=%STEAM_PATH%\%REL_PATH%"

set "FOUND_PATH="

echo ======================================================
echo          PALWORLD SKIN REMOVER (UNINSTALLER)
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
echo Please manually delete the .pak file from:
echo "Palworld\Pal\Content\Paks\~mods"
echo.
pause
exit /b

:FOUND
echo.
echo ✅ Found Path: %FOUND_PATH%
set "MODS_FOLDER=%FOUND_PATH%\~mods"

if not exist "%MODS_FOLDER%" (
    echo 📝 The ~mods folder does not exist. No skins are installed.
    pause
    exit /b
)

echo.
echo 🗑️ Uninstalling specific skin(s)...
set "COUNT=0"

:: Loop through any .pak files in the CURRENT directory
:: and remove them from the ~mods folder if they exist there.
for %%F in (*.pak) do (
    if exist "%MODS_FOLDER%\%%F" (
        echo Removing: %%F
        del /f /q "%MODS_FOLDER%\%%F"
        set /a COUNT+=1
    ) else (
        echo Note: %%F is already not installed.
    )
)

if %COUNT% EQU 0 (
    echo.
    echo 📝 No matching installed skins were found to remove.
) else (
    echo.
    echo ✅ %COUNT% Skin(s) removed successfully!
)

echo.
pause

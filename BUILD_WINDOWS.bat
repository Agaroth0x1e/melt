@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title MelT Build
cd /d "%~dp0"

echo =====================================================
echo Building MelT for Windows
echo =====================================================
echo.

REM Step 1: Install deps
echo [1/6] Installing Python dependencies...
pip install -r requirements.txt
if !ERRORLEVEL! neq 0 ( echo FAILED & pause & exit /b 1 )

REM Step 2: Install PyInstaller
echo [2/6] Installing PyInstaller...
pip install pyinstaller
if !ERRORLEVEL! neq 0 ( echo FAILED & pause & exit /b 1 )

REM Step 3: Generate icon
echo [3/6] Generating icon...
python generate_icon.py

REM Step 4: Find or download ffmpeg
echo [4/6] Locating ffmpeg...
set "FFMPEG_ARG="
set "FFMPEG_DEST=bin\windows\ffmpeg.exe"

if exist "!FFMPEG_DEST!" (
    echo   ffmpeg.exe found in bin\windows
    set "FFMPEG_ARG=--add-data !FFMPEG_DEST!;."
    goto :ffmpeg_ok
)

where ffmpeg >nul 2>&1
if !ERRORLEVEL! equ 0 (
    for /f "delims=" %%i in ('where ffmpeg') do (
        copy /Y "%%i" "!FFMPEG_DEST!" >nul
        set "FFMPEG_ARG=--add-data !FFMPEG_DEST!;."
        goto :ffmpeg_ok
    )
)

echo   ffmpeg not found. Downloading...
powershell -Command "& {Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile 'ffmpeg.zip'}"
if !ERRORLEVEL! equ 0 (
    powershell -Command "& {Expand-Archive -Path 'ffmpeg.zip' -DestinationPath 'ffmpeg_temp' -Force; Copy-Item 'ffmpeg_temp\ffmpeg*\bin\ffmpeg.exe' '!FFMPEG_DEST!'}"
    rmdir /S /Q "ffmpeg_temp" >nul 2>&1
    del "ffmpeg.zip" >nul 2>&1
    if exist "!FFMPEG_DEST!" (
        echo   ffmpeg downloaded and bundled
        set "FFMPEG_ARG=--add-data !FFMPEG_DEST!;."
        goto :ffmpeg_ok
    )
)

echo   WARNING: ffmpeg NOT bundled - .exe will require system ffmpeg
:ffmpeg_ok

REM Step 5: Build
echo [5/6] Building executable...
set SOUNDS_ARG=--add-data "sounds;sounds"
if defined FFMPEG_ARG (
    pyinstaller --onefile --console --name "melt" ^
        --icon "bin\windows\icon.ico" ^
        --add-data "config/config.json;config" ^
        !FFMPEG_ARG! ^
        !SOUNDS_ARG! ^
        --hidden-import "rich" --hidden-import "yt_dlp" ^
        "main.py"
) else (
    pyinstaller --onefile --console --name "melt" ^
        --icon "bin\windows\icon.ico" ^
        --add-data "config/config.json;config" ^
        !SOUNDS_ARG! ^
        --hidden-import "rich" --hidden-import "yt_dlp" ^
        "main.py"
)
if !ERRORLEVEL! neq 0 ( echo FAILED & pause & exit /b 1 )

REM Step 6: Copy output
echo [6/6] Copying output...
copy /Y "dist\melt.exe" "bin\windows\melt.exe" >nul
copy /Y "dist\melt.exe" "bin\host\melt.exe" >nul
if !ERRORLEVEL! neq 0 ( echo FAILED & pause & exit /b 1 )

echo.
echo =====================================================
echo BUILD COMPLETE
echo Output: bin\windows\melt.exe
if defined FFMPEG_ARG ( echo ffmpeg BUNDLED - no system install needed
) else ( echo NOTE: ffmpeg NOT bundled )
echo =====================================================

rmdir /S /Q "build" >nul 2>&1
rmdir /S /Q "dist" >nul 2>&1
del "melt.spec" >nul 2>&1
echo.
pause

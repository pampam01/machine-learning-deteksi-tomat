@echo off
title UJI SERVO 2 (180 DERAJAT / SORTIR KUNING)
cd /d "%~dp0"

echo ============================================================
echo   ALAT UJI SERVO 2 (KUNING / 180 DERAJAT)
echo ============================================================

REM Cek virtual environment
if exist "%~dp0.venv\Scripts\activate.bat" (
    call "%~dp0.venv\Scripts\activate.bat"
) else if exist "%~dp0venv\Scripts\activate.bat" (
    call "%~dp0venv\Scripts\activate.bat"
) else if exist "%~dp0env\Scripts\activate.bat" (
    call "%~dp0env\Scripts\activate.bat"
)

python tests/tes_servo2_180.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ============================================================
    echo [INFO] Jika port error, pastikan kamera jalankan.bat ditutup dulu (tekan 'Q').
    echo ============================================================
    pause
)

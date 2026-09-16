@echo off
title SISTEM PEMILAH TOMAT C4.5
cd /d "%~dp0"

echo ============================================================
echo    SISTEM PEMILAH TOMAT C4.5 - WINDOWS (EZ MODE)
echo ============================================================

REM Cek apakah ada virtual environment di folder lokal
if exist "%~dp0.venv\Scripts\activate.bat" (
    echo [INFO] Mengaktifkan virtual environment .venv...
    call "%~dp0.venv\Scripts\activate.bat"
) else if exist "%~dp0venv\Scripts\activate.bat" (
    echo [INFO] Mengaktifkan virtual environment venv...
    call "%~dp0venv\Scripts\activate.bat"
) else if exist "%~dp0env\Scripts\activate.bat" (
    echo [INFO] Mengaktifkan virtual environment env...
    call "%~dp0env\Scripts\activate.bat"
) else (
    echo [INFO] Menggunakan Python bawaan sistem...
)

echo [INFO] Menjalankan sistem deteksi kamera dan pemilah...
python utama_hsv.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ============================================================
    echo [PERINGATAN] Program berhenti dengan kode status: %ERRORLEVEL%
    echo ============================================================
    pause
)

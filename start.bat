@echo off
title NusaTerminal (FastAPI + Deno)
echo ==================================================
echo   🚀 Menjalankan NusaTerminal (AI Financial App)
echo ==================================================
echo.

REM Pastikan berada di folder script
cd /d "%~dp0"

REM Mengecek apakah Virtual Environment Python ada
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual Environment 'venv' tidak ditemukan!
    echo Silakan buat dengan: python -m venv venv
    pause
    exit /b
)

echo [1/2] Mengaktifkan Virtual Environment...
call venv\Scripts\activate.bat

echo [2/2] Memulai FastAPI Server (Deno API akan otomatis dijalankan oleh main.py)...
echo.
echo ==================================================
echo Tekan CTRL+C untuk mematikan semua server.
echo ==================================================
echo.

"%~dp0venv\Scripts\python.exe" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

pause

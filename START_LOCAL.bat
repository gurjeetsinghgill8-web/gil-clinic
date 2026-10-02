@echo off
title GIL CLINIC - Local Server
cd /d "%~dp0"
echo ============================================
echo   GIL CLINIC - Local Server Start
echo   (Data computer par hi save hota hai)
echo ============================================

REM --- Check Python ---
where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] Python nahi mila.
    echo   1. https://www.python.org/downloads/ se Python 3.11+ install karein
    echo   2. Install karte waqt "Add Python to PATH" ka checkbox tick karein
    echo   3. Ye file dobara chalayein
    echo.
    pause
    exit /b 1
)

REM --- Install dependencies on first run only ---
if not exist ".deps_installed" (
    echo [SETUP] Pehli baar - dependencies install ho rahi hain (internet chahiye)...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Dependency install fail hui. Internet check karein.
        pause
        exit /b 1
    )
    echo ok > .deps_installed
)

REM --- Auto backup before starting ---
echo [BACKUP] Data backup ho raha hai...
python backup_now.py

REM --- Find LAN IP ---
set LANIP=
for /f "tokens=2 delims=:" %%i in ('ipconfig ^| findstr /c:"IPv4"') do set LANIP=%%i
set LANIP=%LANIP: =%

echo.
echo  -------------------------------------------------
echo   Clinic ke dusre computers/mobiles is address se
echo   kholen (dono same WiFi par hone chahiye):
echo.
echo        http://%LANIP%:8000
echo.
echo   Isi computer par:  http://localhost:8000
echo  -------------------------------------------------
echo.
echo  [IMPORTANT]
echo   - Ye window BAND mat karna - server isi se chalta hai
echo   - Pehli baar Windows Firewall puche to "Allow access" dabayein
echo   - Computer sleep na ho iske liye: Settings - System - Power
echo     - Screen and sleep - Never (plugged in)
echo.
echo  Server start ho raha hai... (Ctrl+C se band hota hai)
echo.

start "" cmd /c "timeout /t 4 >nul & start http://localhost:8000"

python -m uvicorn main_v2:app --host 0.0.0.0 --port 8000

echo.
echo Server band ho gaya. Backup le liya gaya tha (backups/ folder mein).
pause

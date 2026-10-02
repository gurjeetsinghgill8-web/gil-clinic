@echo off
title GIL CLINIC - Patient Link Tunnel
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python nahi mila. python.org se install karein.
    pause
    exit /b 1
)

if not exist cloudflared.exe (
    echo [ERROR] cloudflared.exe nahi mila. Pehli baar download karna hoga:
    echo   https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
    echo   is folder mein save karein cloudflared.exe naam se.
    pause
    exit /b 1
)

echo.
echo  Note: Server pehle START_LOCAL.bat se chalu karna hai.
echo  Ye window tunnel ke liye hai — BAND mat karna.
echo.
python start_tunnel.py
pause

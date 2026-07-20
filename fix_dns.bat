@echo off
title GIL CLINIC — DNS Fix for Railway
echo ============================================
echo   GIL CLINIC — DNS Fix Tool
echo   This will add the Railway app domain
echo   to your Windows hosts file.
echo ============================================
echo.
echo URL: https://cardioqueue-production.up.railway.app
echo IP:  69.46.46.126
echo.
echo Requesting administrator privileges...
echo.

:: Request admin elevation
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo This script needs administrator privileges.
    echo Right-click and select "Run as administrator".
    pause
    exit /b 1
)

:: Add entry to hosts file
echo 69.46.46.126    cardioqueue-production.up.railway.app >> %windir%\System32\drivers\etc\hosts

:: Flush DNS cache
ipconfig /flushdns

echo.
echo ✅ Done! The domain has been added to your hosts file.
echo ✅ DNS cache flushed.
echo.
echo Now open this link in your browser:
echo https://cardioqueue-production.up.railway.app
echo.
pause

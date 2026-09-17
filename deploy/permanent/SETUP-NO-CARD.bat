@echo off
REM ==============================================================================
REM  GIL CLINIC - SETUP (bina card, bina kharcha, bina signup)
REM
REM  Is file par DOUBLE-CLICK karein. Ye khud:
REM    1. Python install karti hai (agar nahi hai)
REM    2. App ki files + dependencies setup karti hai
REM    3. App ko permanent server banati hai (boot par auto-start + crash par restart
REM       + health watchdog jo hang hone par bhi restart karta hai)
REM    4. Internet par PERMANENT https:// address deti hai (Tailscale - free, card nahi)
REM    5. Address dikhati hai + browser khol deti hai
REM
REM  Bas 1 baar Google/email se login karna padega (Tailscale ka, FREE - card nahi).
REM ==============================================================================
setlocal
title GIL CLINIC - SETUP (no card needed)
color 0A

REM ---- Admin check (khud elevate karta hai) ----
net session >nul 2>&1
if errorlevel 1 (
  echo.
  echo  Administrator permission maang raha hoon... "Yes" dabayein.
  powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
  exit /b
)

set "ROOT=%~dp0..\.."
pushd "%ROOT%"

echo.
echo  ============================================================
echo    GIL CLINIC - SETUP (bina card)
echo  ============================================================
echo.
echo   Ye window khud sab kuch kar degi. 10-15 minute lag sakte hain.
echo   Window khuli rakhein - beech me band mat karein.
echo.
echo   Beech me ek baar BROWSER khulega (Tailscale login) -
echo   apne Gmail/email se login kar dein. Card NAHI maangta.
echo.
pause

echo.
echo  ---------- STEP 1/2 : App ko permanent server banana ----------
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\deploy\permanent\install-windows-service.ps1" -NoTunnel
if errorlevel 1 goto :failed

echo.
echo  ---------- STEP 2/2 : Permanent public address (https) ----------
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\deploy\permanent\install-permanent-url.ps1" -Provider tailscale
if errorlevel 1 goto :failed

echo.
echo  ============================================================
echo   [OK] POORA HO GAYA
echo  ============================================================
echo.
echo   Upar "AAPKA PERMANENT ADDRESS" wala box dekhein - wahi address
echo   patient ko bhejna hai, aur usi se doctor login karega.
echo.
echo   Test: us address ko PHONE me khol kar dekhein (WiFi band karke bhi).
echo.
echo   Aage kuch bhi chahiye (status / naya code / band karna):
echo     powershell -ExecutionPolicy Bypass -File deploy\permanent\install-permanent-url.ps1 -Status
echo     powershell -ExecutionPolicy Bypass -File deploy\permanent\install-windows-service.ps1 -Uninstall
echo.
pause
popd
exit /b 0

:failed
echo.
echo  ============================================================
echo   [X] KUCH STEP POORA NAHI HUA
echo  ============================================================
echo   Is window ka poora text copy karke bhej dein - main dekh lunga.
echo.
pause
popd
exit /b 1

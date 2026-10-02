@echo off
REM ==============================================================================
REM  GIL CLINIC - ONE CLICK SETUP  (Oracle Cloud Always Free VM par app install)
REM
REM  Aapko sirf 2 cheezein batani hain:
REM    1) VM ka Public IP   (Oracle console se copy)
REM    2) SSH key file      (Oracle se VM banate waqt download hui .key file)
REM
REM  Baaki SAB ye file khud karti hai:
REM    - VM se connect karti hai
REM    - naya code GitHub se laati hai
REM    - app + permanent database + HTTPS + auto-restart + health watchdog +
REM      rozana backup - sab set kar deti hai
REM    - aakhir me aapka ADDRESS dikhati hai aur browser khol deti hai
REM
REM  Chalane ka tarika: is file par DOUBLE-CLICK karein.
REM ==============================================================================
setlocal
title GIL CLINIC - Oracle VM setup
color 0B

echo.
echo  ============================================================
echo    GIL CLINIC - ONE CLICK SETUP  (Oracle Cloud Free VM)
echo  ============================================================
echo.
echo   Ye window khud sab kuch install kar degi.
echo   Beech me 5-8 minute lag sakte hain - window band mat karein.
echo.

REM ---------------------------------------------------------------- STEP 1: IP
echo  STEP 1 - VM ka Public IP
echo  (Oracle console -^> Compute -^> Instances -^> apni VM -^> "Public IP address")
echo.
set "VMIP="
set /p VMIP="  Public IP paste karke ENTER dabayein: "
if not defined VMIP goto :noip
REM (pipe se pehle space nahi - warna ip ke aage space jud jata hai aur check fail hota hai)
echo %VMIP%| findstr /R "^[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*$" >nul
if errorlevel 1 goto :badip

REM ------------------------------------------------------------- STEP 2: SSH key
echo.
echo  STEP 2 - SSH key file (.key)
echo  (jo private key Oracle se VM banate waqt download hui thi - usually Downloads)
echo  Tip: file ko is window par DRAG-AND-DROP bhi kar sakte hain.
echo.
set "FOUNDKEY="
for %%F in ("%USERPROFILE%\Downloads\*.key") do set "FOUNDKEY=%%~fF"
if defined FOUNDKEY echo  Downloads me ye key mili: %FOUNDKEY%
echo  (agar wahi hai to seedha ENTER dabayein, warna apni file ka path dein)
echo.
set "KEYFILE="
set /p KEYFILE="  Key file path: "
if not defined KEYFILE set "KEYFILE=%FOUNDKEY%"
if not defined KEYFILE goto :badkey

:havekey
REM Drag-and-drop ke extra quotes hatao (%~1 se, safe tareeka)
call :strip "%KEYFILE%"
if not exist "%KEYFILE%" goto :badkey

REM Windows par key ki permission theek karo - warna ssh kehta hai
REM "UNPROTECTED PRIVATE KEY FILE ... too open" aur setup wahin ruk jata hai
if not exist "%USERPROFILE%\.ssh" mkdir "%USERPROFILE%\.ssh" >nul 2>&1
copy /Y "%KEYFILE%" "%USERPROFILE%\.ssh\gilclinic_vm_key" >nul 2>&1
if exist "%USERPROFILE%\.ssh\gilclinic_vm_key" set "KEYFILE=%USERPROFILE%\.ssh\gilclinic_vm_key"
icacls "%KEYFILE%" /inheritance:r >nul 2>&1
icacls "%KEYFILE%" /grant:r "%USERNAME%:R" >nul 2>&1

set "VMUSER=ubuntu"
set "VMUSER2="
echo.
set /p VMUSER2="  VM ka username (ENTER = ubuntu): "
if defined VMUSER2 set "VMUSER=%VMUSER2%"

echo.
echo  ============================================================
echo   Connect kar raha hoon:  %VMUSER%@%VMIP%
echo  ============================================================
echo.
echo  (Pehli baar "yes/no" pooch sakta hai - "yes" likh kar ENTER dabayein)
echo.

ssh -i "%KEYFILE%" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=25 %VMUSER%@%VMIP% "echo '--- VM se connection OK ---'; set -e; rm -rf /tmp/gc; git clone --depth=1 https://github.com/gurjeetsinghgill8-web/gil-clinic.git /tmp/gc >/dev/null 2>&1; sudo bash /tmp/gc/deploy/permanent/bootstrap.sh --auto-domain"
if errorlevel 1 goto :setupfail

echo.
echo  ============================================================
echo   [OK] SETUP HO GAYA - app 24/7 chalu hai
echo  ============================================================
echo.
echo   Upar wale box me aapka ADDRESS likha hai (https://....sslip.io)
echo   Usi address se doctor login karein:  /opd/login   (PIN 5554)
echo.
set "MYURL=https://%VMIP:.=-%.sslip.io"
echo   Aapka address: %MYURL%/opd/login
echo.
set "OPENIT="
set /p OPENIT="  Browser me kholun? (Y/N): "
if /I "%OPENIT%"=="Y" start "" "%MYURL%/opd/login"
echo.
echo   Yaad rakhein:
echo     - Oracle console me Public IP ko RESERVED kar dein (free) - phir IP kabhi nahi badlega
echo     - VM par naya update chahiye to:  sudo gilclinic-update
echo     - Backup folder: /opt/gilclinic/data/backups
echo.
pause
exit /b 0

REM ------------------------------------------------------------------ messages
:noip
echo.
echo  [X] IP khali hai - file dobara chalayein.
pause
exit /b 1

:badip
echo.
echo  [X] Ye IP theek nahi lagta: %VMIP%
echo      Oracle console me "Public IP address" copy karein (jaise 152.67.12.34).
pause
exit /b 1

:badkey
echo.
echo  [X] Ye key file nahi mili: %KEYFILE%
echo      Oracle console se VM banate waqt jo private key download hui thi,
echo      uska poora path dein (ya file ko is window par drag-and-drop karein).
pause
exit /b 1

:setupfail
echo.
echo  ============================================================
echo   [X] SETUP POORA NAHI HUA
echo  ============================================================
echo   Sabse common 3 wajah:
echo     1. IP galat hai          - Oracle console me dobara check karein
echo     2. Key file galat hai    - wahi honi chahiye jo VM banate waqt mili thi
echo     3. VM abhi Running nahi  - VM start hone me 2-3 minute lagte hain
echo.
echo   Is window ka poora text copy karke bhej dein - main dekh lunga.
echo.
pause
exit /b 1

:strip
set "KEYFILE=%~1"
exit /b 0

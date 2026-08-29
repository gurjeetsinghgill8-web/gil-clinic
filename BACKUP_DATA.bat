@echo off
title GIL CLINIC - DATA BACKUP
cd /d "%~dp0"
echo ============================================
echo   GIL CLINIC - Data Backup
echo ============================================
python backup_now.py
echo.
echo  [TIP] OneDrive/Google Drive mirror ke liye neeche wali line
echo        mein apna folder path daal kar # hatayein:
echo        python backup_now.py "C:\Users\pc\OneDrive\GIL_CLINIC_BACKUPS"
echo.
pause

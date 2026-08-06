@echo off
REM ═══════════════════════════════════════════════════════════════════
REM GIL CLINIC — Windows Local Setup Script
REM One-click install for doctors. Run as Administrator.
REM ═══════════════════════════════════════════════════════════════════

echo.
echo 🏥 GIL CLINIC — Local Setup
echo ═══════════════════════════════════
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python 3.11+ is required. Download from https://python.org
    echo    Check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
echo ✅ Python found: 
python --version

REM Check pip
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ pip not found. Reinstall Python with pip.
    pause
    exit /b 1
)

echo.
echo 📦 Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ❌ Dependencies installation failed.
    pause
    exit /b 1
)
echo ✅ Dependencies installed.

echo.
echo 🗄️ Setting up database...
if not exist "clinic_data" mkdir clinic_data

echo.
echo ⚙️ Configuration...
if not exist ".env" (
    echo # GIL CLINIC Local Environment > .env
    echo GHOS_DB_URL=sqlite:///./clinic_data/clinic.db >> .env
    echo GHOS_DB_URL_ASYNC=sqlite+aiosqlite:///./clinic_data/clinic.db >> .env
    echo GHOS_DEV_AUTH_BYPASS=true >> .env
    echo SECRET_KEY=local-clinic-secret-change-in-production >> .env
    echo. >> .env
    echo 📝 Created .env file. Add your GROQ_API_KEY for AI features:
    echo    GROQ_API_KEY=your_key_here >> .env
)

echo.
echo 🚀 Starting GIL CLINIC...
echo    Open browser: http://localhost:8000
echo    Press Ctrl+C to stop.
echo.
python -m uvicorn main_v2:app --host 0.0.0.0 --port 8000 --reload

pause

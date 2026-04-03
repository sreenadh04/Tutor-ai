@echo off
SETLOCAL

echo ╔══════════════════════════════════════════╗
echo ║      MediTutor AI — Windows Setup        ║
echo ╚══════════════════════════════════════════╝
echo.

REM Check Python
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Download from: https://www.python.org/downloads/
    pause & exit /b 1
)

echo [1/5] Creating virtual environments...
cd backend
python -m venv venv
call venv\Scripts\activate
echo [2/5] Installing backend dependencies (this takes 3-5 minutes)...
pip install -r requirements.txt
deactivate
cd ..

cd frontend
python -m venv venv
call venv\Scripts\activate
echo [3/5] Installing frontend dependencies...
pip install -r requirements.txt
deactivate
cd ..

echo [4/5] Copying .env file...
IF NOT EXIST .env (
    copy .env.example .env
    echo [!] Created .env file — EDIT IT with your API keys before starting!
)

echo [5/5] Setup complete!
echo.
echo ════════════════════════════════════════════
echo  NEXT STEPS:
echo  1. Edit .env and add your API keys
echo  2. Run: start_backend.bat
echo  3. Run: start_frontend.bat  (in a new terminal)
echo  4. Open: http://localhost:8501
echo ════════════════════════════════════════════
pause

@echo off
echo Starting MediTutor AI Backend...
cd backend
call venv\Scripts\activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause

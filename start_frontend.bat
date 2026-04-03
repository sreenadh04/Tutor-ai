@echo off
echo Starting MediTutor AI Frontend...
cd frontend
call venv\Scripts\activate
streamlit run app.py
pause

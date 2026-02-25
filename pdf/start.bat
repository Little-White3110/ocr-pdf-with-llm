@echo off
echo Starting PDF OCR Web Application...
echo.

echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

echo.
echo Installing backend dependencies...
cd backend
pip install -r requirements.txt

echo.
echo Starting backend server...
start "PDF OCR Backend" cmd /k python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

cd ..

echo.
echo Starting frontend server...
cd frontend
start "PDF OCR Frontend" cmd /k python -m http.server 8080

cd ..

echo.
echo ========================================
echo Application is starting...
echo Backend: http://localhost:8000
echo Frontend: http://localhost:8080
echo ========================================
echo.

timeout /t 3 >nul
start http://localhost:8080

pause

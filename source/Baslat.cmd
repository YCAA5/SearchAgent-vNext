@echo off
cd /d "%~dp0"
if exist "..\application\SearchAgent\SearchAgent.exe" (
    start "" "..\application\SearchAgent\SearchAgent.exe"
    exit /b 0
)
if not exist ".venv\Scripts\python.exe" (
    echo Projenin Python ortami bulunamadi: .venv\Scripts\python.exe
    pause
    exit /b 1
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause

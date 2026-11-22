@echo off
REM Earnings Pattern Screener - one-click launcher for Windows.
REM First run creates a private Python environment and installs dependencies (a few minutes).
REM   run.bat            start the app
REM   run.bat --demo     start with simulated data (no internet needed)
REM   run.bat --update   reinstall / upgrade dependencies (e.g. if Yahoo changes and yfinance needs an update)
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python environment...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo.
        echo Python 3.10+ is required. Install it from https://www.python.org/downloads/
        echo and tick "Add python.exe to PATH" during setup, then run this file again.
        pause
        exit /b 1
    )
)

if "%1"=="--update" del ".venv\installed.flag" 2>nul

if not exist ".venv\installed.flag" (
    echo Installing dependencies - this only happens once...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install --upgrade -r requirements.txt
    if errorlevel 1 (
        echo Dependency install failed. See messages above.
        pause
        exit /b 1
    )
    echo ok> ".venv\installed.flag"
)

if "%1"=="--update" (
    start "" ".venv\Scripts\pythonw.exe" main.py
) else (
    start "" ".venv\Scripts\pythonw.exe" main.py %*
)

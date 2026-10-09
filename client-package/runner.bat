@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ===============================================
echo Flipkart Cookie Refresh
echo ===============================================

echo This will set up everything needed, then open Flipkart login.

title Flipkart Cookie Refresh

call :ensure_chrome
call :ensure_python

if "%PYTHON_CMD%"=="" (
    echo Python still could not be found after setup.
    echo Please install Python manually from: https://www.python.org/downloads/
    echo Make sure "Add Python to PATH" is selected.
    pause
    exit /b 1
)

echo.
echo Installing requirements...
"%PYTHON_CMD%" -m pip install --upgrade pip
"%PYTHON_CMD%" -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo Failed to install Python packages.
    echo Please check internet access and try again.
    pause
    exit /b 1
)

echo.
echo Opening Flipkart login window...
"%PYTHON_CMD%" flipkart_login.py

if errorlevel 1 (
    echo.
    echo Login script failed to start.
    echo Please check the error above and try again.
    pause
    exit /b 1
)

echo.
echo Finished. You can close this window.
pause >nul
exit /b 0

:ensure_chrome
where chrome >nul 2>nul
if not errorlevel 1 exit /b 0
where google-chrome >nul 2>nul
if not errorlevel 1 exit /b 0
where winget >nul 2>nul
if errorlevel 1 (
    echo Chrome is not installed and winget is unavailable.
    echo Please install Google Chrome manually from https://www.google.com/chrome/
    echo Then run this file again.
    pause
    exit /b 1
)

echo Chrome not found. Installing Google Chrome...
winget install --id Google.Chrome --source winget --accept-source-agreements --accept-package-agreements --silent
if errorlevel 1 (
    echo Chrome install failed.
    echo Please install Chrome manually from https://www.google.com/chrome/
    pause
    exit /b 1
)

echo Chrome installed successfully.
exit /b 0

:ensure_python
set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 (
    py --version >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py" & exit /b 0
)

where python >nul 2>nul
if not errorlevel 1 (
    python --version >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python" & exit /b 0
)

where winget >nul 2>nul
if errorlevel 1 (
    echo Python was not found and winget is unavailable.
    echo Please install Python manually from: https://www.python.org/downloads/
    echo Make sure "Add Python to PATH" is selected.
    pause
    exit /b 1
)

echo Python was not found. Installing Python 3.12...
winget install --id Python.Python.3.12 --source winget --accept-source-agreements --accept-package-agreements --silent
if errorlevel 1 (
    echo Python install failed.
    echo Please install Python manually from: https://www.python.org/downloads/
    echo Make sure "Add Python to PATH" is selected.
    pause
    exit /b 1
)

where py >nul 2>nul
if not errorlevel 1 (
    py --version >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py" & exit /b 0
)
where python >nul 2>nul
if not errorlevel 1 (
    python --version >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python" & exit /b 0
)

echo Python is installed but not available on PATH yet.
echo Please close this window and run the file again once the installation finishes.
pause
exit /b 1

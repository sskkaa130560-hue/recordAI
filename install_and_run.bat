@echo off
chcp 65001 >nul 2>&1
title RecordAI — Voice Recorder

echo ============================================
echo   RecordAI — Voice Recorder Setup
echo ============================================
echo.

REM Try to find Python
where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
    goto :found
)

where python3 >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python3"
    goto :found
)

where py >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py"
    goto :found
)

REM Check common installation paths
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
    "C:\Python39\python.exe"
) do (
    if exist %%P (
        set "PYTHON_CMD=%%~P"
        goto :found
    )
)

echo [ERROR] Python is not installed on this system.
echo.
echo Please install Python 3.9+ from:
echo   https://www.python.org/downloads/
echo.
echo During installation, check the box:
echo   "Add Python to PATH"
echo.
pause
exit /b 1

:found
echo [OK] Found Python: %PYTHON_CMD%
echo.

REM Check Python version
%PYTHON_CMD% --version
echo.

REM Clear proxy settings that can cause SOCKS errors
set "HTTP_PROXY="
set "HTTPS_PROXY="
set "ALL_PROXY="
set "http_proxy="
set "https_proxy="
set "all_proxy="

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo [*] Creating virtual environment...
    %PYTHON_CMD% -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment already exists.
)
echo.

REM Activate virtual environment
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

REM Install / update dependencies
echo [*] Installing dependencies...
pip install --no-proxy -r requirements.txt
if %errorlevel% neq 0 (
    echo [*] Retrying without --no-proxy flag...
    pip install -r requirements.txt
)
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo.
echo [OK] All dependencies installed.
echo.
echo ============================================
echo   Starting RecordAI...
echo ============================================
echo.

REM Run the application
python recorder.py

REM Keep window open if the app crashed
if %errorlevel% neq 0 (
    echo.
    echo [!] The application exited with an error.
    pause
)

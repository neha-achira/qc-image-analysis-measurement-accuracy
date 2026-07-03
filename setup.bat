@echo off
title Cartridge QC — Setup
echo.
echo  ============================================
echo   Cartridge QC Setup — Achira Labs
echo  ============================================
echo.

:: Check Python is installed
py --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  ERROR: Python is not installed.
    echo.
    echo  Please install Python from:
    echo    https://www.python.org/downloads/
    echo.
    echo  During install, tick "Add Python to PATH"
    echo  then re-run this setup.
    echo.
    pause
    exit /b 1
)

echo  Python found:
py --version
echo.

:: Bootstrap pip in case it is missing
echo  Checking pip...
py -m ensurepip --upgrade >nul 2>&1

:: Install dependencies
echo  Installing required packages (opencv, numpy, scipy)...
echo  This may take a minute on first run.
echo.
py -m pip install --upgrade pip >nul 2>&1
py -m pip install -r "%~dp0requirements.txt"

if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Package installation failed.
    echo  Check your internet connection and try again.
    pause
    exit /b 1
)

echo.
echo  ============================================
echo   Setup complete!
echo  ============================================
echo.
echo  To run calibration:
echo    py calibrate.py calibrate --ref Holes_ch00.png --feature hole --n_holes 3
echo.
echo  Or double-click  run_calibrate.bat
echo.
pause

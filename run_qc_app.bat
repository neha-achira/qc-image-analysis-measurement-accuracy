@echo off
title Achira Beta Cartridge QC
cd /d "%~dp0"
py qc_app.py
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: App failed to start. Run setup.bat first.
    pause
)

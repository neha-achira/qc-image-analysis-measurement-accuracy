@echo off
title Cartridge QC — Calibration
cd /d "%~dp0"
echo.
echo  ============================================
echo   Cartridge QC Calibration — ACMCTA001
echo  ============================================
echo.
echo  Usage examples:
echo.
echo  [1] Calibrate holes image (recommended — 3 holes):
echo      py calibrate.py calibrate --ref Holes_ch00.png --feature hole --n_holes 3
echo.
echo  [2] Calibrate neck image:
echo      py calibrate.py calibrate --ref neck_ch00.png --feature channel --n_holes 1
echo.
echo  [3] Check current calibration:
echo      py calibrate.py info
echo.
echo  [4] Verify calibration drift:
echo      py calibrate.py verify --image Holes_ch00.png
echo.
echo  ── Zoom controls (in the image window) ─────────────────────
echo  Scroll wheel = zoom in/out    Right-drag = pan
echo  0 = reset zoom                + / - = zoom from centre
echo  ────────────────────────────────────────────────────────────
echo.
set /p CMD= Enter command (or press ENTER to run default calibration):

if "%CMD%"=="" (
    set CMD=py calibrate.py calibrate --ref Holes_ch00.png --feature hole --n_holes 3
)

echo.
echo  Running: %CMD%
echo.
%CMD%
echo.
pause

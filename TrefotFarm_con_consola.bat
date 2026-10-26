@echo off
REM Igual que TrefotFarm.bat pero con consola, para ver errores si no abre.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
where py >nul 2>nul
if %errorlevel%==0 (
    py -3.12 -u TrefotFarm.pyw
) else (
    python -u TrefotFarm.pyw
)
pause

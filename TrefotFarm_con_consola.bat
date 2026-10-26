@echo off
REM Igual que TrefotFarm.bat pero con consola, para ver errores si no abre.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
where python >nul 2>nul
if %errorlevel%==0 (
    python -u TrefotFarm.pyw
) else (
    py -u TrefotFarm.pyw
)
pause

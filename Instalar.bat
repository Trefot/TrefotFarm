@echo off
REM Instala lo que necesita TrefotFarm v2 (una sola vez). Requiere Python 3.12.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3.12 -m pip install -r requirements.txt
) else (
    python -m pip install -r requirements.txt
)
pause

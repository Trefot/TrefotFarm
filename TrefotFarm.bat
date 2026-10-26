@echo off
REM Abre la interfaz de TrefotFarm v2 (sin consola).
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw TrefotFarm.pyw
) else (
    start "" pyw TrefotFarm.pyw
)

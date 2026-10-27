@echo off
REM Abre la interfaz de LumenFarm v2 (sin consola).
REM Usa el lanzador oficial de Python (pyw) para no caer en el atajo de la Microsoft Store.
cd /d "%~dp0"
where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw -3.12 LumenFarm.pyw
) else (
    start "" pythonw LumenFarm.pyw
)

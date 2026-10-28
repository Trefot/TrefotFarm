@echo off
REM Pasa las pruebas del bot (no usa el juego ni el raton). Tardan unos 20 segundos.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3.12 -m unittest discover -s pruebas -t pruebas
) else (
    python -m unittest discover -s pruebas -t pruebas
)
pause

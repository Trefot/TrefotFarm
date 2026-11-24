@echo off
REM Prueba si el bot podria farmear sin mover el raton ni tener el juego delante (no cambia nada del bot).
REM Se abre como administrador, igual que el juego.
cd /d "%~dp0"
net session >nul 2>&1
if not %errorlevel%==0 (
    powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
    exit /b
)
where py >nul 2>nul
if %errorlevel%==0 (
    py -3.12 -m lumen.segundo_plano
) else (
    python -m lumen.segundo_plano
)
pause

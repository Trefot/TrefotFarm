"""Rutas del proyecto. Todo se resuelve desde la carpeta raiz de LumenFarm."""

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ASSETS = RAIZ / "assets"
IMAGENES = ASSETS / "imagenes"  # plantillas generales del juego
EQUIPO = ASSETS / "equipo"  # tus capturas de cartas (una subcarpeta por equipo)
MODELOS = ASSETS / "modelos"
CAPTURAS = RAIZ / "capturas"
LOGS = RAIZ / "logs"
CONFIG = RAIZ / "config.yaml"

for carpeta in (EQUIPO, CAPTURAS, LOGS):
    carpeta.mkdir(parents=True, exist_ok=True)

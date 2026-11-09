"""Conocimiento de cada jefe que ensena el jugador (paso 3 de IA.md), en lumen/datos/conocimiento.yaml.

Por destino y fase: "preferir" un tipo de carta (area o de un objetivo) y "evitar" otros (ulti, area, uno). Lo usa el
juego inteligente (Jugador.elegir) como un multiplicador mas, despues de las pasivas y antes de lo aprendido en cada
pelea. Asi, cuando el jugador explica un jefe nuevo, se anade al archivo sin tocar codigo.
"""

from functools import lru_cache
from pathlib import Path

import yaml

ARCHIVO = Path(__file__).resolve().parents[1] / "datos" / "conocimiento.yaml"
PREFERIR = 1.6
EVITAR = 0.3


@lru_cache(maxsize=1)
def _datos() -> dict:
    try:
        return yaml.safe_load(ARCHIVO.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}


def reglas(destino: str, fase, datos: dict | None = None) -> dict:
    """Las reglas de ese destino y fase (las de "todas" y, encima, las de la fase)."""
    datos = _datos() if datos is None else datos
    jefe = datos.get(destino) or {}
    salida: dict = {}
    for clave in ("todas", fase, str(fase) if fase is not None else None):
        if clave is not None and isinstance(jefe.get(clave), dict):
            salida.update(jefe[clave])
    return salida


def _tipo(nombre: str, es_area) -> str:
    base = (nombre or "").split("@")[0]
    if base.endswith(".ulti"):
        return "ulti"
    try:
        return "area" if es_area and es_area(base) else "uno"
    except Exception:
        return "uno"


def aplicar(valores: dict, destino: str, fase, es_area=None, datos: dict | None = None) -> tuple[dict, dict]:
    """(valores con lo que ensena el jugador para ese destino y fase, motivos por carta)."""
    r = reglas(destino, fase, datos)
    if not r:
        return valores, {}
    preferir = r.get("preferir")
    evitar = set(r.get("evitar") or [])
    salida, motivos = {}, {}
    for nombre, valor in valores.items():
        tipo = _tipo(nombre, es_area)
        f = 1.0
        if preferir and tipo == preferir:
            f *= PREFERIR
        if tipo in evitar:
            f *= EVITAR
        salida[nombre] = valor * f
        if f != 1.0:
            motivos[nombre] = [f"lo que me ensenaste x{f:.2f}"]
    return salida, motivos

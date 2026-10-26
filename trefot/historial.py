"""Historial de sesiones de farmeo (logs/historial.jsonl, una linea por sesion)."""

import json
import time

from trefot.rutas import LOGS

ARCHIVO = LOGS / "historial.jsonl"


def registrar(sesion: dict) -> None:
    with ARCHIVO.open("a", encoding="utf-8") as f:
        f.write(json.dumps(sesion, ensure_ascii=False) + "\n")


def leer(limite: int = 500) -> list[dict]:
    """Sesiones, la mas reciente primero."""
    if not ARCHIVO.is_file():
        return []
    sesiones = []
    for linea in ARCHIVO.read_text(encoding="utf-8").splitlines():
        try:
            sesiones.append(json.loads(linea))
        except json.JSONDecodeError:
            continue
    return sesiones[::-1][:limite]


def totales(sesiones: list[dict]) -> dict:
    t = {"sesiones": len(sesiones), "victorias": 0, "derrotas": 0, "reinicios": 0, "pociones": 0, "segundos": 0}
    for s in sesiones:
        for clave in ("victorias", "derrotas", "reinicios", "pociones"):
            t[clave] += int(s.get(clave, 0))
        t["segundos"] += max(0, s.get("fin", 0) - s.get("inicio", 0))
    peleas = t["victorias"] + t["derrotas"] + t["reinicios"]
    t["tasa"] = 100 * t["victorias"] / peleas if peleas else 0.0
    t["por_hora"] = t["victorias"] / (t["segundos"] / 3600) if t["segundos"] > 60 else 0.0
    return t


def hoy(sesiones: list[dict]) -> list[dict]:
    inicio_dia = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
    return [s for s in sesiones if s.get("inicio", 0) >= inicio_dia]

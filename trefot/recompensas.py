"""Recompensas: foto de la pantalla de Victory de cada pelea y lo que salio en ella.

Cada victoria guarda una foto en recompensas/<AAAA-MM-DD>/ y una linea en recompensas/indice.jsonl
con lo leido por trefot/botin.py: {"objetos": {id_objeto: cantidad}, "oro": int}.
Las fotos de antes de que existiera la lectura se analizan con ``reanalizar_pendientes``.
"""

import json
import threading
import time
from pathlib import Path

import numpy as np

from trefot import botin
from trefot.rutas import RAIZ
from trefot.vision import guardar_imagen, leer_imagen

CARPETA = RAIZ / "recompensas"
INDICE = CARPETA / "indice.jsonl"
_lock = threading.Lock()


def _analizar(pantalla) -> dict:
    try:
        return botin.analizar(pantalla)
    except Exception:  # una lectura fallida nunca debe parar el bot
        return {"objetos": {}, "oro": None, "error_lectura": True}


def guardar(pantalla: np.ndarray, *, modo: str, nombre_modo: str, sesion: float, victoria: int) -> Path:
    ahora = time.time()
    carpeta = CARPETA / time.strftime("%Y-%m-%d", time.localtime(ahora))
    ruta = carpeta / f"{time.strftime('%H%M%S', time.localtime(ahora))}_{modo}_v{victoria}.png"
    guardar_imagen(ruta, pantalla)
    registro = {
        "ruta": ruta.relative_to(CARPETA).as_posix(),
        "fecha": ahora,
        "modo": modo,
        "nombre_modo": nombre_modo,
        "sesion": sesion,
        "victoria": victoria,
        **_analizar(pantalla),
        "analizado": True,
    }
    with _lock:
        CARPETA.mkdir(parents=True, exist_ok=True)
        with INDICE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    return ruta


def _leer_indice() -> list[dict]:
    if not INDICE.is_file():
        return []
    registros = []
    for linea in INDICE.read_text(encoding="utf-8").splitlines():
        try:
            registros.append(json.loads(linea))
        except json.JSONDecodeError:
            continue
    return registros


def leer() -> list[dict]:
    """Registros cuya foto todavia existe, el mas reciente primero."""
    registros = []
    for r in _leer_indice():
        r["ruta_completa"] = CARPETA / r["ruta"]
        if r["ruta_completa"].is_file():
            registros.append(r)
    return registros[::-1]


def reanalizar_pendientes(todas: bool = False) -> int:
    """Lee el botin de las fotos que aun no se analizaron (o de todas). Devuelve cuantas analizo."""
    with _lock:
        registros = _leer_indice()
        hechas = 0
        for r in registros:
            if r.get("analizado") and not todas:
                continue
            pantalla = leer_imagen(CARPETA / r["ruta"])
            if pantalla is None:
                continue
            r.update(_analizar(pantalla))
            r["analizado"] = True
            hechas += 1
        if hechas:
            INDICE.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in registros), encoding="utf-8")
        return hechas


def totales_objetos(registros: list[dict]) -> dict[str, int]:
    """Suma por objeto (id del catalogo -> cantidad total), de mayor a menor."""
    total: dict[str, int] = {}
    for r in registros:
        for oid, cantidad in (r.get("objetos") or {}).items():
            total[oid] = total.get(oid, 0) + int(cantidad)
    return dict(sorted(total.items(), key=lambda kv: -kv[1]))


def total_oro(registros: list[dict]) -> int:
    return sum(int(r.get("oro") or 0) for r in registros)

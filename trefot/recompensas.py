"""Fotos de las pantallas de recompensas.

Cada victoria guarda una foto en recompensas/<AAAA-MM-DD>/ y una linea en recompensas/indice.jsonl.
El campo "objetos" queda vacio por ahora: cuando exista el reconocimiento de objetos se rellenara
({"nombre": cantidad}) y la pagina Recompensas mostrara los totales sin cambiar nada mas.
"""

import json
import threading
import time
from pathlib import Path

import numpy as np

from trefot.rutas import RAIZ
from trefot.vision import guardar_imagen

CARPETA = RAIZ / "recompensas"
INDICE = CARPETA / "indice.jsonl"
_lock = threading.Lock()


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
        "objetos": {},
    }
    with _lock:
        CARPETA.mkdir(parents=True, exist_ok=True)
        with INDICE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    return ruta


def leer() -> list[dict]:
    """Registros cuya foto todavia existe, el mas reciente primero."""
    if not INDICE.is_file():
        return []
    registros = []
    for linea in INDICE.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(linea)
        except json.JSONDecodeError:
            continue
        r["ruta_completa"] = CARPETA / r["ruta"]
        if r["ruta_completa"].is_file():
            registros.append(r)
    return registros[::-1]


def totales_objetos(registros: list[dict]) -> dict[str, int]:
    """Suma de objetos reconocidos (vacio hasta que exista el reconocimiento)."""
    total: dict[str, int] = {}
    for r in registros:
        for nombre, cantidad in (r.get("objetos") or {}).items():
            total[nombre] = total.get(nombre, 0) + int(cantidad)
    return dict(sorted(total.items(), key=lambda kv: -kv[1]))

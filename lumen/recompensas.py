"""Recompensas: foto de la pantalla de Victory de cada pelea y lo que salio en ella.

Cada victoria guarda una foto en recompensas/<AAAA-MM-DD>/ y una linea en recompensas/indice.jsonl
con lo leido por lumen/botin.py: {"objetos": {id_objeto: cantidad}, "oro": int}.
Las fotos de antes de que existiera la lectura se analizan con ``reanalizar_pendientes``.
"""

import json
import threading
import time
from pathlib import Path

import numpy as np

from lumen import botin
from lumen.rutas import RAIZ
from lumen.vision import guardar_imagen, leer_imagen

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


def _reescribir_objetos(cambio) -> None:
    """Aplica ``cambio(objetos) -> objetos`` a todos los registros del indice."""
    with _lock:
        registros = _leer_indice()
        for r in registros:
            r["objetos"] = cambio(dict(r.get("objetos") or {}))
        INDICE.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in registros), encoding="utf-8")


def unir_objeto(origen: str, destino: str) -> None:
    """``origen`` era ``destino`` leido raro: desde ahora cuenta como el, tambien en lo ya guardado."""
    catalogo = botin.cargar_catalogo()
    catalogo.setdefault(origen, {})["unido_a"] = destino
    botin.guardar_catalogo(catalogo)

    def cambio(objetos):
        if origen in objetos:
            objetos[destino] = objetos.get(destino, 0) + objetos.pop(origen)
        return objetos

    _reescribir_objetos(cambio)


def descartar_objeto(oid: str) -> None:
    """No era un objeto (p. ej. un cofre a medio abrir): se quita de todo y no se vuelve a contar."""
    catalogo = botin.cargar_catalogo()
    catalogo.setdefault(oid, {})["descartado"] = True
    botin.guardar_catalogo(catalogo)
    _reescribir_objetos(lambda objetos: {k: v for k, v in objetos.items() if k != oid})


def unir_repetidos_de_galeria() -> int:
    """Objetos del botin vinculados al mismo objeto de la galeria (p. ej. uno leido de una foto movida):
    se unen al primero. Devuelve cuantos unio."""
    catalogo = botin.cargar_catalogo()
    primero: dict[str, str] = {}
    unidos = 0
    for oid in botin.visibles(catalogo):
        gid = (catalogo.get(oid) or {}).get("galeria")
        if not gid:
            continue
        if gid in primero:
            unir_objeto(oid, primero[gid])
            catalogo = botin.cargar_catalogo()
            catalogo[oid]["unido_auto"] = True  # union hecha por el bot (se deshace si el vinculo era malo)
            botin.guardar_catalogo(catalogo)
            unidos += 1
        else:
            primero[gid] = oid
    return unidos


def deshacer_uniones_malas() -> int:
    """Uniones hechas porque dos objetos tenian el mismo de la galeria, cuando uno de esos vinculos ya no
    vale (p. ej. el cubo gris tomado por Blue Magic Essence): se separan y se releen las fotos para que
    cada uno recupere sus cantidades. Devuelve cuantas deshizo."""
    catalogo = botin.cargar_catalogo()
    deshechas = 0
    for oid, datos in catalogo.items():
        destino = (datos or {}).get("unido_a")
        gid = (datos or {}).get("galeria")
        if destino and gid and (catalogo.get(destino) or {}).get("galeria") != gid:
            datos.pop("unido_a", None)
            datos.pop("unido_auto", None)
            deshechas += 1
    if deshechas:
        botin.guardar_catalogo(catalogo)
        reanalizar_pendientes(todas=True)
    return deshechas


def horas_de(registros: list[dict], sesiones_historial: list[dict]) -> float:
    """Horas farmeando en las sesiones de esos registros (del historial; si falta, de la primera
    a la ultima foto)."""
    por_inicio = {round(s.get("inicio", 0)): s for s in sesiones_historial}
    segundos = 0.0
    for inicio in {r.get("sesion", 0) for r in registros}:
        s = por_inicio.get(round(inicio))
        if s:
            segundos += max(0.0, s.get("fin", inicio) - s.get("inicio", inicio))
        else:
            fotos = [r["fecha"] for r in registros if r.get("sesion") == inicio]
            segundos += max(fotos) - inicio if fotos else 0
    return segundos / 3600


def totales_objetos(registros: list[dict]) -> dict[str, int]:
    """Suma por objeto (id del catalogo -> cantidad total), de mayor a menor."""
    total: dict[str, int] = {}
    for r in registros:
        for oid, cantidad in (r.get("objetos") or {}).items():
            total[oid] = total.get(oid, 0) + int(cantidad)
    return dict(sorted(total.items(), key=lambda kv: -kv[1]))


def total_oro(registros: list[dict]) -> int:
    return sum(int(r.get("oro") or 0) for r in registros)

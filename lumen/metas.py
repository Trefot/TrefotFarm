"""Metas de material: "quiero 40 Garras de Skoll y Hati" y cuanto falta.

Cada meta se guarda en config.yaml ("metas": [{"objeto", "tengo", "quiero", "desde"}]): ``tengo`` es lo
que el jugador dijo tener en el momento ``desde``; a eso se suma el botin que el bot reconoce en cada
victoria posterior (lumen/recompensas.py). Un objeto del botin cuenta para la meta si esta unido a ese
objeto de las tablas de premios ("premio" en el catalogo del botin, ver recompensas.vincular_premios).
"""

import math
import time
from dataclasses import dataclass

from lumen import botin, config, premios, recompensas
from lumen.modos import MODOS

REFRESCO_S = 5.0  # Inicio y Farmear las piden a menudo: se releen como mucho cada 5 s
_cache: tuple[float, list] = (0.0, [])
_vinculado = 0.0


@dataclass
class Meta:
    objeto: str
    tengo: int
    quiero: int
    desde: float
    conseguido: int = 0  # lo que sumo el botin desde ``desde``

    @property
    def nombre(self) -> str:
        return premios.info(self.objeto).get("nombre", self.objeto)

    @property
    def actual(self) -> int:
        return self.tengo + self.conseguido

    @property
    def faltan(self) -> int:
        return max(0, self.quiero - self.actual)

    @property
    def completa(self) -> bool:
        return self.actual >= self.quiero


def _guardadas() -> list[dict]:
    return [m for m in (config.obtener("metas") or []) if m.get("objeto")]


def cargar(fresco: bool = False) -> list[Meta]:
    """Las metas con lo que ya sumo el botin."""
    global _cache
    if not fresco and time.time() - _cache[0] < REFRESCO_S:
        return list(_cache[1])
    metas = [Meta(m["objeto"], int(m.get("tengo", 0)), int(m.get("quiero", 1)), float(m.get("desde", 0)))
             for m in _guardadas()]
    if metas:
        _vincular()
        registros = recompensas.leer()
        catalogo = botin.cargar_catalogo()
        for meta in metas:
            meta.conseguido = conseguido(meta.objeto, meta.desde, registros, catalogo)
    _cache = (time.time(), metas)
    return list(metas)


def _vincular():
    """Une con las tablas de premios los objetos nuevos del botin (como mucho una vez por minuto)."""
    global _vinculado
    if time.time() - _vinculado < 60:
        return
    _vinculado = time.time()
    try:
        recompensas.vincular_premios()
    except Exception:  # una lectura fallida no debe romper las metas
        pass


def de(objeto: str, metas: list[Meta] | None = None) -> Meta | None:
    return next((m for m in (cargar() if metas is None else metas) if m.objeto == objeto), None)


def poner(objeto: str, tengo: int, quiero: int) -> None:
    """Crea la meta o la cambia (lo que tienes cuenta desde ahora)."""
    global _cache
    otras = [m for m in _guardadas() if m["objeto"] != objeto]
    nueva = {"objeto": objeto, "tengo": int(tengo), "quiero": int(quiero), "desde": time.time()}
    viejas = [m["objeto"] for m in _guardadas()]
    otras.insert(viejas.index(objeto) if objeto in viejas else len(otras), nueva)  # conserva su sitio
    config.guardar({"metas": otras})
    _cache = (0.0, [])


def quitar(objeto: str) -> None:
    global _cache
    config.guardar({"metas": [m for m in _guardadas() if m["objeto"] != objeto]})
    _cache = (0.0, [])


# ------------------------------------------------------------------ botin
def objeto_de_botin(oid: str, catalogo: dict) -> str | None:
    """El objeto de las tablas de premios que es un objeto del botin."""
    real = botin.destino(oid, catalogo)
    return (catalogo.get(real) or {}).get("premio") if real else None


def conseguido(objeto: str, desde: float, registros: list[dict], catalogo: dict) -> int:
    total = 0
    for r in registros:
        if float(r.get("fecha") or 0) < desde:
            continue
        for oid, cantidad in (r.get("objetos") or {}).items():
            if objeto_de_botin(oid, catalogo) == objeto:
                total += int(cantidad)
    return total


# ------------------------------------------------------------------ donde farmearla
def mejor_destino(objeto: str) -> tuple[str, float] | None:
    """(destino, media por victoria) donde mas da de los que el bot ya sabe farmear."""
    opciones = [(d, premios.esperado(d, objeto)) for d in premios.donde_sale(objeto) if d in MODOS]
    opciones = [o for o in opciones if o[1] > 0]
    return max(opciones, key=lambda o: o[1]) if opciones else None


def victorias_para(faltan: int, por_victoria: float) -> int:
    return math.ceil(faltan / por_victoria) if por_victoria > 0 and faltan > 0 else 0


def del_destino(id_destino: str, metas: list[Meta]) -> list[Meta]:
    """Las metas sin completar que este destino ayuda a llenar (para parar al cumplirlas)."""
    return [m for m in metas if not m.completa and premios.esperado(id_destino, m.objeto) > 0]

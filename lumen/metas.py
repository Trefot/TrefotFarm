"""Metas de material: "quiero 40 Garras de Skoll y Hati" y cuanto falta.

Cada meta se guarda en config.yaml ("metas": [{"objeto", "tengo", "quiero", "desde"}]): ``tengo`` es lo
que el jugador dijo tener en el momento ``desde``. A eso se suma el botin que el bot reconoce en cada
victoria posterior (lumen/recompensas.py). El botin usa su propio catalogo (objeto_1, objeto_2...);
un objeto cuenta para la meta si esta unido a la ficha de la galeria que lleva el objeto en
lumen/datos/premios.yaml ("galeria"). Los que no tienen ficha se ajustan a mano.
"""

import math
import time
from dataclasses import dataclass

from lumen import botin, config, premios, recompensas
from lumen.modos import MODOS


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

    @property
    def cuenta_sola(self) -> bool:
        """El bot la va llenando con el botin (si no, solo cambia a mano)."""
        return bool(premios.info(self.objeto).get("galeria"))


def _guardadas() -> list[dict]:
    return [m for m in (config.obtener("metas") or []) if m.get("objeto")]


def cargar(registros: list[dict] | None = None) -> list[Meta]:
    """Las metas con lo que ya sumo el botin (``registros``: los de recompensas.leer(), para no releerlos)."""
    metas = [Meta(m["objeto"], int(m.get("tengo", 0)), int(m.get("quiero", 1)), float(m.get("desde", 0)))
             for m in _guardadas()]
    if metas:
        registros = recompensas.leer() if registros is None else registros
        catalogo = botin.cargar_catalogo()
        for meta in metas:
            meta.conseguido = conseguido(meta.objeto, meta.desde, registros, catalogo)
    return metas


def de(objeto: str, metas: list[Meta] | None = None) -> Meta | None:
    return next((m for m in (cargar() if metas is None else metas) if m.objeto == objeto), None)


def poner(objeto: str, tengo: int, quiero: int) -> None:
    """Crea la meta o la cambia (lo que tienes cuenta desde ahora)."""
    otras = [m for m in _guardadas() if m["objeto"] != objeto]
    otras.append({"objeto": objeto, "tengo": int(tengo), "quiero": int(quiero), "desde": time.time()})
    config.guardar({"metas": otras})


def quitar(objeto: str) -> None:
    config.guardar({"metas": [m for m in _guardadas() if m["objeto"] != objeto]})


# ------------------------------------------------------------------ botin
def objeto_de_botin(oid: str, catalogo: dict) -> str | None:
    """El objeto de premios.yaml que es un objeto del botin (por su ficha de la galeria)."""
    real = botin.destino(oid, catalogo)
    gid = (catalogo.get(real) or {}).get("galeria") if real else None
    return premios.por_galeria().get(gid) if gid else None


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
    return next(((d, e) for d, e in premios.donde_sale(objeto) if d in MODOS), None)


def victorias_para(faltan: int, por_victoria: float) -> int:
    return math.ceil(faltan / por_victoria) if por_victoria > 0 and faltan > 0 else 0


def del_destino(id_destino: str, metas: list[Meta]) -> list[Meta]:
    """Las metas sin completar que este destino ayuda a llenar (para parar al cumplirlas)."""
    return [m for m in metas if not m.completa and m.cuenta_sola and premios.esperado(id_destino, m.objeto) > 0]

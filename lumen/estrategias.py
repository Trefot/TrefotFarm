"""Estrategias de pelea por equipo (lumen/datos/estrategias.yaml): que carta jugar primero.

El bot reconoce el equipo por las cartas de la mano: la estrategia cuyo equipo tenga mas cartas
reconocidas (al menos MIN_CARTAS) es la que usa. Luego, en cada hueco del turno, juega la carta jugable
de mas prioridad (y entre iguales, la de mas rango).
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from lumen.cartas import NO_JUGABLES, Carta, Rango
from lumen.equipo import Equipo, Puesto

ARCHIVO = Path(__file__).resolve().parent / "datos" / "estrategias.yaml"
MIN_CARTAS = 3  # cartas reconocidas en la mano para dar por bueno el equipo
ORDEN_RANGO = {Rango.ORO: 0, Rango.PLATA: 1, Rango.BRONCE: 2, Rango.ULTI: 0, Rango.NINGUNO: 3}


@dataclass
class Estrategia:
    nombre: str
    equipo: list[str]
    prioridad: list[str]
    _equipo: Equipo | None = field(default=None, repr=False)

    @property
    def reconocedor(self) -> Equipo:
        if self._equipo is None:
            self._equipo = Equipo(self.nombre, self.nombre, [Puesto("", (), pid) for pid in self.equipo], set())
        return self._equipo

    def etiquetar(self, mano: list[Carta]) -> int:
        """Pone nombre a las cartas de la mano; devuelve cuantas reconocio."""
        self.reconocedor.etiquetar(mano)
        return sum(1 for c in mano if c.nombre)

    def elegir(self, mano: list[Carta]) -> Carta | None:
        """La carta a jugar ahora (o None si no hay ninguna de la lista)."""
        candidatas = [c for c in mano if c.tipo not in NO_JUGABLES and c.nombre in self.prioridad]
        if not candidatas:
            return None
        return min(candidatas, key=lambda c: (self.prioridad.index(c.nombre), ORDEN_RANGO.get(c.rango, 3), -c.posicion))


def la_de_mas_rango(mano: list[Carta]) -> Carta | None:
    """Si ninguna carta de la mano esta en la prioridad: la jugable de mas rango, para no quedarse parado."""
    jugables = [c for c in mano if c.tipo not in NO_JUGABLES]
    if not jugables:
        return None
    return min(jugables, key=lambda c: (ORDEN_RANGO.get(c.rango, 3), -c.posicion))


def cargar(contenido: str) -> list[Estrategia]:
    if not ARCHIVO.is_file():
        return []
    with ARCHIVO.open(encoding="utf-8") as f:
        datos = (yaml.safe_load(f) or {}).get(contenido) or []
    return [Estrategia(d.get("nombre", ""), list(d.get("equipo") or []), list(d.get("prioridad") or [])) for d in datos]


def reconocer(estrategias: list[Estrategia], mano: list[Carta]) -> Estrategia | None:
    """La estrategia del equipo que esta en la mano (o None si ninguna encaja)."""
    mejor, mejor_n = None, MIN_CARTAS - 1
    for e in estrategias:
        n = e.etiquetar([Carta(c.posicion, c.rect, c.imagen, c.tipo, c.rango) for c in mano])
        if n > mejor_n:
            mejor, mejor_n = e, n
    return mejor

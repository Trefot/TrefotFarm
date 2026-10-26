"""Armador de equipos: con los personajes que tienes, que equipos puedes armar para cada contenido.

Cada modo declara sus puestos (funcion + roles necesarios + personaje recomendado). Un sustituto
es un personaje tuyo, fuera del equipo recomendado, que tiene todos los roles del puesto.
Ojo: el bot solo juega el guion con el equipo recomendado; los sustitutos son para jugar a mano
o como base de un guion nuevo.
"""

from dataclasses import dataclass, field

from trefot.equipo import Equipo, Puesto
from trefot.personajes import Personaje

LISTO = "listo"
CON_SUSTITUTOS = "con_sustitutos"
INCOMPLETO = "incompleto"


@dataclass
class AnalisisPuesto:
    puesto: Puesto
    recomendado: Personaje | None
    lo_tienes: bool
    sustitutos: list[Personaje] = field(default_factory=list)
    elegido: Personaje | None = None  # quien lo ocuparia con lo que tienes


@dataclass
class AnalisisEquipo:
    estado: str
    puestos: list[AnalisisPuesto]

    @property
    def faltan(self) -> list[AnalisisPuesto]:
        return [a for a in self.puestos if not a.lo_tienes]


def analizar(equipo: Equipo, biblioteca: dict[str, Personaje]) -> AnalisisEquipo:
    mios = [pj for pj in biblioteca.values() if pj.tengo]
    analisis = []
    for puesto in equipo.puestos:
        rec = biblioteca.get(puesto.recomendado)
        lo_tienes = bool(rec and rec.tengo)
        sustitutos = [
            pj for pj in mios
            if pj.id not in equipo.orden and all(rol in pj.roles for rol in puesto.roles)
        ]
        analisis.append(AnalisisPuesto(puesto, rec, lo_tienes, sustitutos, rec if lo_tienes else None))

    # Repartir sustitutos sin repetir personaje (primero los puestos con menos opciones).
    usados = {a.elegido.id for a in analisis if a.elegido}
    for a in sorted((a for a in analisis if not a.lo_tienes), key=lambda a: len(a.sustitutos)):
        a.elegido = next((pj for pj in a.sustitutos if pj.id not in usados), None)
        if a.elegido:
            usados.add(a.elegido.id)

    if all(a.lo_tienes for a in analisis):
        estado = LISTO
    elif all(a.elegido for a in analisis):
        estado = CON_SUSTITUTOS
    else:
        estado = INCOMPLETO
    return AnalisisEquipo(estado, analisis)

"""Reglas de Ratatoskr (Floor 1-3), tal como las explico el usuario jugando una partida (2026-11-09).

La rata esta siempre subida a uno de sus 3 troncos (1 en el centro, 2 a la izquierda, 3 a la derecha). Las cartas
que ponen una desventaja la mueven: Bleed -> tronco 3, Shock -> tronco 2, Poison -> tronco 1. Una desventaja que la
mandaria al tronco donde ya esta no se puede usar (el juego la bloquea; si solo quedan esas, "Move a skill or lock
the slot").

- Floor 1: atacar a la rata. Si el turno acaba sin matarla, mejor dejarla en otro tronco (si no, el siguiente
  turno las cartas que la llevan ahi quedan bloqueadas).
- Floor 2: es inmortal mientras vivan los troncos 2 y 3: romper los dos, mejor con cartas de area (sin area, de un
  objetivo, a uno y otro para dejarlos parejos). No moverla mientras haya troncos; despues las desventajas sirven
  para limpiar la mano, guardando un Poison por si sale fuera del centro.
- Floor 3: hay que llevarla a un tronco concreto (fase 1 -> 3, fase 2 -> 2, fase 3 -> 3). Va ahi cuando acumula una
  desventaja de cada tipo: se guardan las 3 cartas y se lanzan en el mismo turno. Las ultis la mueven al azar: nada
  de ultis hasta tenerla colocada (salvo como ultimo recurso, con el tronco 2 roto y sin las 3 desventajas). Ya
  colocada: romper los otros troncos (con escudo rebota el dano: no pegarle a ella) y rematarla al final con todo.
  Para la fase siguiente hay que volver a tener las 3 desventajas en la mano.

Aqui solo estan las reglas (sin pantalla): que cartas no jugar, cuales jugar ya y a quien apuntar.
"""

import re
from dataclasses import dataclass, field

DESTINO = {"bleed": 3, "shock": 2, "poison": 1}  # a que tronco manda cada desventaja
TRONCO_FASE_F3 = {1: 3, 2: 2, 3: 3}  # Floor 3: donde hay que dejarla en cada fase

# Frases que APLICAN una desventaja (no las que solo la nombran: "Release ... damage in Shock, Poison, and Bleed")
_APLICA = {
    "bleed": re.compile(r"bleeds? for|makes? [^.]{0,40}bleed|inflicts? bleed|applies \d* ?bleed", re.I),
    "shock": re.compile(r"shocks? for|inflicts? shock|applies \d* ?shock|makes? [^.]{0,40}shock", re.I),
    "poison": re.compile(r"poisons? for|inflicts? poison|applies \d* ?poison|makes? [^.]{0,40}poison", re.I),
}


def desventajas_del_texto(texto: str) -> set[str]:
    t = re.sub(r"\[[0-9A-Fa-f]{6}\]|\[-\]", "", texto or "")
    t = re.sub(r"release:[^.]*\.", "", t, flags=re.I)  # la definicion de "Release" nombra las tres
    return {d for d, patron in _APLICA.items() if patron.search(t)}


_PALABRA = {"poison": "poison", "bleed": "bleed", "shock": "shock"}
_PASIVA = re.compile(r"(all-target|single-target) attack[^.]*?(poison|bleed|shock)", re.I)
_A_TODOS = re.compile(r"on all enemies|all-target", re.I)


def desventajas_de_pasiva(texto: str) -> dict[str, set[str]]:
    """Desventajas que la pasiva del heroe anade a sus ataques: {"area": {...}, "uno": {...}}. P. ej. Valenti azul:
    "If the hero uses an all-target attack and deals damage, enemies hit by the attack are Poisoned" -> sus cartas
    de area ponen Poison (lo senalo el usuario, 2026-11-09)."""
    t = re.sub(r"\[[0-9A-Fa-f]{6}\]|\[-\]", "", texto or "")
    salida = {"area": set(), "uno": set()}
    for alcance, palabra in _PASIVA.findall(t):
        salida["area" if alcance.lower().startswith("all") else "uno"].add(palabra.lower())
    return salida


def es_de_area(texto: str) -> bool:
    return bool(_A_TODOS.search(texto or ""))


@dataclass
class CartaRata:
    indice: int  # posicion en la mano
    desventajas: set[str] = field(default_factory=set)
    ulti: bool = False
    area: bool = False
    jugable: bool = True
    pasiva: set[str] = field(default_factory=set)  # las que pone solo la pasiva (el juego no mira esas para dejarla)


@dataclass
class Decision:
    bloquear: set[int] = field(default_factory=set)  # no jugarlas (aunque el juego deje)
    forzar: set[int] = field(default_factory=set)  # jugar una de estas ahora (si hay)
    objetivo: object = "rata"  # "rata" o el numero del tronco (1, 2, 3)
    motivo: str = ""


def _una_de_cada(cartas: list[CartaRata], tipos=("bleed", "shock", "poison")) -> dict[str, int]:
    elegidas = {}
    for tipo in tipos:
        for c in cartas:
            if c.jugable and tipo in c.desventajas and c.indice not in elegidas.values():
                elegidas[tipo] = c.indice
                break
    return elegidas


def decidir(piso: int, fase: int, rata_en: int | None, vivos: set[int], cartas: list[CartaRata],
            restantes: int, ultima_del_turno: bool, puestas: set[str] | None = None) -> Decision:
    """``vivos``: troncos que siguen en pie. ``restantes``: acciones que quedan en el turno (esta incluida).
    ``puestas``: desventajas que ya se le pusieron este turno (para acabar el trio empezado)."""
    puestas = set(puestas or ())
    d = Decision()
    con_desventaja = [c for c in cartas if c.desventajas and c.jugable]
    for c in con_desventaja:  # las que la mandarian donde ya esta: el juego no las deja
        propias = c.desventajas - c.pasiva
        if rata_en is not None and propias and all(DESTINO[x] == rata_en for x in propias):
            d.bloquear.add(c.indice)

    if piso == 1:
        if ultima_del_turno and rata_en is not None:
            mover = [c.indice for c in con_desventaja if c.indice not in d.bloquear]
            if mover:
                d.forzar = set(mover)
                d.motivo = "acaba el turno: la muevo de tronco para no quedar bloqueado"
        return d

    if piso == 2:
        # El usuario (2026-11-09): solo romper los troncos 2 y 3 y luego mucho dano. El 1 (centro) NO se rompe: roto,
        # la rata queda inmortal. Subida encima del 1 lo protege; si se baja, el area lo rompe. Bleed y Shock la sacan
        # del centro, Poison la devuelve.
        troncos = sorted(vivos & {2, 3})
        fuera = rata_en in (2, 3) or (rata_en is None and 1 in vivos)  # la espiral del 1 se ve: no esta encima
        venenos = [c.indice for c in con_desventaja if "poison" in c.desventajas]
        d.bloquear |= {c.indice for c in con_desventaja if c.desventajas & {"bleed", "shock"}}
        d.objetivo = troncos[0] if troncos else "rata"
        if fuera and venenos:
            d.forzar = set(venenos)
            d.bloquear -= d.forzar
            d.motivo = "no esta encima del tronco 1: la devuelvo al centro con Poison"
        elif fuera:
            d.bloquear |= {c.indice for c in cartas if c.area or c.ulti}  # que el area no rompa el tronco 1
            d.motivo = "no esta encima del tronco 1 y no tengo Poison: nada de area para no romperlo"
        elif troncos:
            d.motivo = "rompo los troncos 2 y 3"
        else:
            d.motivo = "troncos 2 y 3 rotos: mucho dano a la rata"
        return d

    # Floor 3
    destino = TRONCO_FASE_F3.get(fase, 3)
    if rata_en != destino:
        # Se mueve al tener una de cada (el orden da igual). Si ya se empezo el trio este turno, se acaba con las que
        # faltan (prueba del 2026-11-09: jugaba la primera y despues, con 2 en la mano, guardaba las otras).
        faltan = tuple(x for x in ("bleed", "shock", "poison") if x not in puestas)
        trio = _una_de_cada(cartas, faltan)
        ultis = [c.indice for c in cartas if c.ulti and c.jugable]
        if puestas and not faltan:
            d.bloquear |= {c.indice for c in con_desventaja}  # ya tiene las 3: guardarlas para la fase siguiente
            d.bloquear |= set(ultis)
            d.motivo = f"ya tiene las 3 desventajas: va al tronco {destino}"
        elif faltan and len(trio) == len(faltan) and restantes >= len(faltan):
            d.forzar = set(trio.values())
            d.motivo = (f"le faltan {', '.join(faltan)}: las pongo para llevarla al tronco {destino}" if puestas
                        else f"tengo las 3 desventajas: la llevo al tronco {destino}")
        else:
            d.bloquear |= {c.indice for c in con_desventaja}  # guardarlas hasta tener las 3
            if 2 not in vivos and ultis and len(trio) < 3:
                d.forzar = set(ultis)  # ultimo recurso: la ulti la mueve al azar
                d.motivo = "sin las 3 desventajas y el tronco 2 roto: pruebo la ulti"
            else:
                d.bloquear |= set(ultis)  # la moveria al azar
                d.motivo = "guardo las desventajas hasta tener las 3; sin ultis"
        otros = sorted(vivos - {destino})
        d.objetivo = 2 if 2 in otros else (otros[0] if otros else "rata")
        if d.forzar and not (d.forzar & set(ultis)):
            d.objetivo = "rata"  # las desventajas tienen que caerle a ella (la de un objetivo iba al tronco marcado)
        return d
    # Colocada: romper los otros troncos y despues rematarla
    otros = sorted(vivos - {destino})
    if fase < 3:
        guardar = _una_de_cada(cartas)  # para la fase siguiente hacen falta otra vez las 3
        d.bloquear |= set(guardar.values())
    if otros:
        d.objetivo = otros[0]
        d.bloquear |= {c.indice for c in cartas if c.ulti or c.area}  # no pegarle a ella (su escudo rebota)
        d.motivo = f"colocada en el {destino}: rompo los otros troncos"
    else:
        d.objetivo = "rata"
        d.motivo = "sin troncos: la remato con todo"
    return d

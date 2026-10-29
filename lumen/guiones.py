"""Guiones de pelea: como jugar un jefe con un equipo, fase a fase y turno a turno, en un archivo.

Un guion (lumen/datos/guiones/<id>.yaml) dice, para cada fase y turno, que hacer en cada hueco:
una carta concreta, una de un color, la ulti de alguien, cualquiera o mover. Cada hueco puede dar
alternativas y se usa la primera que se pueda (el formato esta explicado en ciervo_piso4.yaml).
Si no se puede ninguna, como haria el jugador: fusionar moviendo y esperar al turno siguiente; y si
tampoco hay nada que fusionar, rendirse y reiniciar.

``EstrategiaGuion`` tiene la misma forma que la estrategia de Perros piso 4 (``decidir``), asi que
un modo de Floor 4 solo tiene que usarla con su guion. Los colores salen del atributo de cada heroe
(lumen/datos/personajes.yaml) y los nombres de las cartas son los del equipo ("heroe.carta").

Orbes de la ulti: el juego no se lee todavia; se cuentan aqui (cada carta jugada o movida de un
heroe le suma uno; su ulti los vacia). Sirven para "mover la carta del que menos orbes tenga".
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from lumen import personajes as P
from lumen.cartas import Carta, Rango, TipoCarta
from lumen.modos.perros_piso4 import Estrategia, Reiniciar

CARPETA = Path(__file__).resolve().parent / "datos" / "guiones"
COLORES = ("rojo", "verde", "azul")  # los del semaforo
FUSIONABLES = (Rango.BRONCE, Rango.PLATA)


@dataclass
class Guion:
    id: str
    nombre: str
    equipo: list[str]
    alias: dict[str, str]
    fases: dict[int, dict]
    colores: dict[str, str] = field(default_factory=dict)  # heroe -> rojo | verde | azul ...

    @classmethod
    def cargar(cls, id_guion: str, biblioteca: dict | None = None) -> "Guion":
        datos = yaml.safe_load((CARPETA / f"{id_guion}.yaml").read_text(encoding="utf-8")) or {}
        biblioteca = P.cargar() if biblioteca is None else biblioteca
        equipo = list(datos.get("equipo") or [])
        return cls(id_guion, datos.get("nombre", id_guion), equipo, dict(datos.get("alias") or {}),
                   {int(f): d or {} for f, d in (datos.get("fases") or {}).items()},
                   {pid: biblioteca[pid].color for pid in equipo if pid in biblioteca})

    def pasos(self, fase: int, turno: int) -> list:
        turnos = (self.fases.get(fase) or {}).get("turnos") or {}
        return turnos.get(turno) or turnos.get("resto") or []

    def guardar(self, fase: int):
        return (self.fases.get(fase) or {}).get("guardar") or []


def heroe(carta: Carta) -> str | None:
    return carta.nombre.split(".")[0] if carta.nombre else None


def es_ulti(carta: Carta) -> bool:
    return carta.tipo == TipoCarta.ULTI or (carta.nombre or "").endswith(".ulti")


class EstrategiaGuion(Estrategia):
    def __init__(self, guion: Guion):
        self.guion = guion
        self.orbes: dict[str, int] = {pid: 0 for pid in guion.equipo}
        self._turno: tuple[int, int] | None = None
        self._jugadas: dict[int, Carta] = {}  # accion -> carta jugada en este turno
        self._color_turno: str | None = None
        self._esperando = False  # este turno ya no sigue el guion: solo fusionar o mover

    # ------------------------------------------------------------------ decidir
    def decidir(self, fase: int, turno: int, accion: int, mano: list[Carta], total: int = 4):
        if self._turno != (fase, turno):
            self._turno, self._jugadas, self._color_turno, self._esperando = (fase, turno), {}, None, False
        self._jugadas.pop(accion, None)  # si se vuelve a pedir la misma accion, cuenta la nueva
        if not self._esperando:
            pasos = self.guion.pasos(fase, turno)
            if not pasos:
                raise Reiniciar(f"el guion no dice que hacer en la fase {fase}")
            paso = pasos[min(accion, len(pasos) - 1)]
            for alternativa in (paso if isinstance(paso, list) else [paso]):
                eleccion = self._resolver(alternativa, fase, mano)
                if eleccion is not None:
                    return self._apuntar(eleccion, mano, accion), None, False
            self._esperando = True  # como el jugador: fusionar y esperar, o reiniciar
            fusion = self._fusion(mano)
            if fusion is None:
                raise Reiniciar(f"F{fase}T{turno}: no puedo seguir el guion ({_texto(paso)}) ni fusionar")
            return self._apuntar(fusion, mano, accion), None, False
        eleccion = self._fusion(mano) or self._mover(mano)
        if eleccion is None:
            raise Reiniciar(f"F{fase}T{turno}: no hay cartas que mover")
        return self._apuntar(eleccion, mano, accion), None, False

    def _apuntar(self, eleccion, mano: list[Carta], accion: int):
        """Anota la jugada (orbes y color del turno) y la devuelve tal cual para el modo."""
        carta = mano[eleccion[0]] if isinstance(eleccion, tuple) else mano[eleccion]
        pid = heroe(carta)
        if pid in self.orbes:
            self.orbes[pid] = 0 if (es_ulti(carta) and not isinstance(eleccion, tuple)) else self.orbes[pid] + 1
        if not isinstance(eleccion, tuple):
            self._jugadas[accion] = carta
            self._color_turno = self._color_turno or self.color(carta)
        return eleccion

    # ------------------------------------------------------------------ pasos
    def _resolver(self, paso, fase: int, mano: list[Carta]):
        protegidas = self._protegidas(fase, mano)
        if paso == "mover":
            return self._mover(mano)
        if paso == "cualquiera":
            return self._mejor(mano, lambda c: c.posicion not in protegidas, semaforo=self._semaforo(fase, mano))
        if not isinstance(paso, dict):
            raise ValueError(f"paso desconocido en el guion: {paso!r}")
        if "carta" in paso:
            nombre = self.guion.alias.get(paso["carta"], paso["carta"])
            return self._mejor(mano, lambda c: c.nombre == nombre)
        if "ulti" in paso:
            return self._mejor(mano, lambda c: c.nombre == f"{paso['ulti']}.ulti")
        if "color" in paso:
            color = paso["color"]
            if color == "el_que_mas":
                color = self._color_mas_repetido(mano, protegidas)
                if color is None:
                    return None
                self._color_turno = color
            elif color == "igual":
                color = self._color_turno
            return self._mejor(mano, lambda c: self.color(c) == color and c.posicion not in protegidas)
        raise ValueError(f"paso desconocido en el guion: {paso!r}")

    def color(self, carta: Carta) -> str | None:
        return self.guion.colores.get(heroe(carta) or "")

    def _protegidas(self, fase: int, mano: list[Carta]) -> set[int]:
        """Cartas que el guion guarda en esta fase (p. ej. la ulti de Freyr para el turno 3)."""
        guardar = self.guion.guardar(fase)
        if not isinstance(guardar, list):
            return set()
        nombres = {self.guion.alias.get(g, g) for g in guardar}
        return {c.posicion for c in mano if c.nombre in nombres}

    def _semaforo(self, fase: int, mano: list[Carta]) -> set[int]:
        """Con guardar: semaforo, la ultima carta de cada color no se gasta en "cualquiera"."""
        if self.guion.guardar(fase) != "semaforo":
            return set()
        ultimas = set()
        for color in COLORES:
            del_color = [c for c in mano if c.jugable and not es_ulti(c) and self.color(c) == color]
            if len(del_color) == 1:
                ultimas.add(del_color[0].posicion)
        return ultimas

    def _color_mas_repetido(self, mano: list[Carta], protegidas: set[int]) -> str | None:
        cuenta = {col: sum(1 for c in mano if c.jugable and c.posicion not in protegidas and self.color(c) == col)
                  for col in COLORES}
        color, n = max(cuenta.items(), key=lambda kv: kv[1])
        return color if n else None

    @staticmethod
    def _mejor(mano: list[Carta], filtro, semaforo: set[int] = frozenset()) -> int | None:
        """La de mas rango que pase el filtro (las ultis, despues de las normales; a igualdad, la de
        mas a la derecha). Las del semaforo, solo si no queda otra."""
        candidatas = [c for c in mano if c.jugable and filtro(c)]
        if not candidatas:
            return None
        libres = [c for c in candidatas if c.posicion not in semaforo]
        if not libres:
            return None
        rango = lambda c: c.rango.value if c.rango != Rango.NINGUNO else -1  # noqa: E731
        return max(libres, key=lambda c: (not es_ulti(c), rango(c), c.posicion)).posicion

    # ------------------------------------------------------------------ mover
    def _fusion(self, mano: list[Carta]) -> tuple[int, int] | None:
        """Mover una carta sobre su gemela (mismo heroe y carta, bronce o plata): se fusionan."""
        for i, a in enumerate(mano):
            for b in mano[i + 1:]:
                if a.jugable and b.jugable and a.nombre and a.nombre == b.nombre and a.rango == b.rango \
                        and a.rango in FUSIONABLES:
                    return (b.posicion, a.posicion)
        return None

    def _mover(self, mano: list[Carta]) -> tuple[int, int] | None:
        """Mover una carta del heroe con menos orbes (sobre su gemela si la hay; si no, sobre la de al lado)."""
        movibles = [c for c in mano if c.tipo not in (TipoCarta.SUELO, TipoCarta.NINGUNA)]
        if len(movibles) < 2:
            return None
        con_heroe = [c for c in movibles if heroe(c) in self.orbes] or movibles
        origen = min(con_heroe, key=lambda c: (self.orbes.get(heroe(c) or "", 99), -c.posicion))
        gemela = next((c for c in movibles if c is not origen and c.nombre and c.nombre == origen.nombre
                       and c.rango == origen.rango and c.rango in FUSIONABLES), None)
        if gemela is not None:
            return (origen.posicion, gemela.posicion)
        i = movibles.index(origen)
        vecina = movibles[i - 1] if i > 0 else movibles[i + 1]
        return (origen.posicion, vecina.posicion)


def _texto(paso) -> str:
    return " o ".join(map(str, paso)) if isinstance(paso, list) else str(paso)

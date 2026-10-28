"""Juego inteligente: piensa el turno entero en vez de carta por carta.

No toca la pantalla. Con la mano leida y las acciones que quedan en el turno, prueba todas las
secuencias de jugadas (jugar una carta o arrastrarla sobre su gemela para fusionarlas) y elige la
que deja mas valor: el dano de este turno MAS lo que valdra la mano para el siguiente.

Reglas de la mano que se simulan (las de 7DS Grand Cross):
- Al jugar una carta se quita de la mano; si sus vecinas quedan juntas y son la misma carta y el
  mismo rango (bronce o plata), se fusionan en una de rango mayor (en cadena).
- Arrastrar una carta sobre su gemela (misma carta y rango) las fusiona: gasta la accion sin atacar.
- La ulti no tiene rango y no se fusiona.

Que cartas son "la misma" se sabe por su nombre (si el equipo tiene capturas) o, si no, por su
dibujo (``agrupar_por_dibujo``): asi funciona con cualquier equipo.

El valor de cada carta es aproximado (VALOR_RANGO, VALOR_ULTI): sirve para comparar jugadas entre si,
no para saber el dano real. Se puede afinar por carta con ``valores`` (p. ej. sacado del texto de la
carta: "200% of Attack on all enemies").
"""

from dataclasses import dataclass
from functools import lru_cache

import cv2
import numpy as np

from lumen.cartas import Carta, Rango, TipoCarta

VALOR_RANGO = {Rango.BRONCE: 1.0, Rango.PLATA: 1.6, Rango.ORO: 2.6}
VALOR_ULTI = 4.0
PESO_FUTURO = 0.45  # cuanto cuenta lo que deja la mano para el turno siguiente frente al dano de ahora
ACCIONES_SIGUIENTE = 4  # cartas que se podran jugar en el turno siguiente (para valorar la mano que queda)
SOLO_AREA_RESTO = 0.2  # en las fases de "solo area", lo que vale una carta de un objetivo frente a lo normal
VALOR_NUEVA = 1.1  # lo que se espera de cada carta nueva que rellena la mano (casi siempre bronce; a veces fusiona)
MISMO_DIBUJO = 8.0  # distancia de dibujo (0-100, ver agrupar_por_dibujo) por debajo: es la misma carta
SUBIR = {Rango.BRONCE: Rango.PLATA, Rango.PLATA: Rango.ORO}


@dataclass(frozen=True)
class Ficha:
    """Una carta de la mano reducida a lo que importa para pensar."""

    nombre: str | None  # None = no se sabe que carta es (no se fusiona con nada)
    rango: Rango
    ulti: bool
    jugable: bool
    valor: float  # dano relativo si se juega

    def gemela(self, otra: "Ficha") -> bool:
        return (self.nombre is not None and self.nombre == otra.nombre and self.rango == otra.rango
                and self.rango in SUBIR and not self.ulti and not otra.ulti)

    def subida(self, valores: dict) -> "Ficha":
        rango = SUBIR[self.rango]
        return Ficha(self.nombre, rango, False, self.jugable, valor_de(self.nombre, rango, False, valores))


def valor_de(nombre: str | None, rango: Rango, ulti: bool, valores: dict) -> float:
    """Dano relativo de una carta. ``valores``: nombre -> multiplicador de esa carta (1.0 = normal)."""
    base = valores.get(nombre, 1.0) if nombre else 1.0
    return base * (VALOR_ULTI if ulti else VALOR_RANGO.get(rango, 1.0))


def _fusionar(mano: tuple, i: int) -> tuple:
    """Fusiones en cadena alrededor de la posicion i (tras quitar o mover una carta)."""
    mano = list(mano)
    valores = _VALORES_ACTUALES
    i = max(0, min(i, len(mano) - 1))
    cambio = True
    while cambio:
        cambio = False
        for k in range(max(0, i - 1), min(len(mano) - 1, i + 1)):
            if mano[k].gemela(mano[k + 1]):
                mano[k : k + 2] = [mano[k].subida(valores)]
                i, cambio = k, True
                break
    return tuple(mano)


_VALORES_ACTUALES: dict = {}


def jugar(mano: tuple, i: int) -> tuple[float, tuple]:
    """(dano, mano que queda) al jugar la carta i."""
    dano = mano[i].valor
    resto = mano[:i] + mano[i + 1 :]
    return dano, (_fusionar(resto, i) if resto else resto)


def mover(mano: tuple, i: int, j: int) -> tuple:
    """Arrastrar la carta i sobre su gemela j: quedan fusionadas en la posicion de j."""
    subida = mano[j].subida(_VALORES_ACTUALES)
    lista = list(mano)
    lista[j] = subida
    del lista[i]
    return _fusionar(tuple(lista), j - 1 if i < j else j)


def valor_futuro(mano: tuple, tamano: int) -> float:
    """Lo que vale la mano para el turno siguiente: al empezarlo se rellena hasta ``tamano`` con cartas
    nuevas; cuentan las mejores que se podran jugar, mas un extra por gemelas separadas por una carta
    (al jugar la del medio se fusionan). Por eso fusionar es bueno: deja sitio a una carta nueva."""
    jugables = [f.valor for f in mano if f.jugable] + [VALOR_NUEVA] * max(0, tamano - len(mano))
    extra = sum(0.3 for a, b in zip(mano, mano[2:]) if a.gemela(b))
    return sum(sorted(jugables, reverse=True)[:ACCIONES_SIGUIENTE]) + extra


@lru_cache(maxsize=50_000)
def _mejor(mano: tuple, acciones: int, tamano: int, arrastrar: bool = True) -> tuple[float, tuple]:
    """(puntuacion, plan) de la mejor secuencia de ``acciones`` jugadas. Plan: (("jugar", i) | ("mover", i, j), ...)."""
    if acciones == 0 or not mano:
        return PESO_FUTURO * valor_futuro(mano, tamano), ()
    opciones = []
    for i, f in enumerate(mano):
        if f.jugable:
            dano, resto = jugar(mano, i)
            puntos, plan = _mejor(resto, acciones - 1, tamano, arrastrar)
            opciones.append((dano + puntos, (("jugar", i),) + plan))
    for i, f in enumerate(mano if arrastrar else ()):  # arrastrar sobre una gemela (solo las que no estan ya al lado: esas ya se habrian fusionado)
        for j, g in enumerate(mano):
            if f.jugable and i != j and abs(i - j) > 1 and f.gemela(g):
                puntos, plan = _mejor(mover(mano, i, j), acciones - 1, tamano, arrastrar)
                opciones.append((puntos, (("mover", i, j),) + plan))
    if not opciones:  # nada que jugar ni fusionar: el turno se pierde
        return PESO_FUTURO * valor_futuro(mano, tamano), ()
    # Empates: preferir jugar a mover y, entre jugadas, la carta mas a la derecha (como una persona).
    return max(opciones, key=lambda o: (round(o[0], 6), o[1][0][0] == "jugar", o[1][0][1]))


def planear(mano: list[Carta], acciones: int, valores: dict | None = None, arrastrar: bool = True) -> tuple[float, tuple]:
    """El mejor plan para lo que queda del turno. ``mano``: la leida de la pantalla (con sus huecos)."""
    global _VALORES_ACTUALES
    valores = valores or {}
    if valores != _VALORES_ACTUALES:
        _VALORES_ACTUALES = dict(valores)
        _mejor.cache_clear()
    fichas = tuple(_ficha(c, valores) for c in mano if c.tipo not in (TipoCarta.SUELO, TipoCarta.NINGUNA))
    return _mejor(fichas, max(0, acciones), max(len(fichas), _tamano(mano)), arrastrar)


class Jugador:
    """Lo que usan los modos: reconoce las cartas (dibujo + base de heroes), las tasa y planea.

    ``elegir`` devuelve la primera jugada del mejor plan con posiciones de pantalla: ("jugar", pos) o
    ("mover", pos_origen, pos_destino), o None si no hay nada que hacer. ``arrastrar=False`` para los
    contenidos donde no se sabe si se pueden arrastrar cartas (demonios).
    """

    def __init__(self, enemigos: int = 1, arrastrar: bool = True):
        self.enemigos = enemigos
        self.arrastrar = arrastrar
        self.solo_area = False  # True: las cartas de un objetivo casi no valen (todos los enemigos a la vez)
        self._indice = self._tasador = None  # se cargan en la primera jugada (tardan ~1 s)

    def _identificar(self, carta: Carta) -> str | None:
        if self._indice is None:
            from lumen import valor_cartas  # aqui: solo se cargan si se juega en modo inteligente
            from lumen.modos.aprender import IndiceCartas

            self._indice = IndiceCartas()
            self._tasador = valor_cartas.Tasador(self.enemigos)
        return self._indice.carta_de(carta)

    def elegir(self, mano: list[Carta], acciones: int) -> tuple | None:
        agrupar_por_dibujo(mano, self._identificar)
        valores = self._tasador.valores(c.nombre for c in mano) if self._tasador else {}
        if self.solo_area and self._tasador:
            # Fase en que todos los enemigos tienen que caer a la vez (fase 3 de los perros de Floor 1-3):
            # areas y ultis primero; las de un objetivo solo si no queda otra cosa.
            valores = {n: v if self._tasador.es_area(n) else v * SOLO_AREA_RESTO for n, v in valores.items()}
        _, plan = planear(mano, acciones, valores, self.arrastrar)
        if not plan:
            return None
        reales = posiciones_reales(mano)
        paso = plan[0]
        return ("jugar", reales[paso[1]]) if paso[0] == "jugar" else ("mover", reales[paso[1]], reales[paso[2]])


def _tamano(mano: list[Carta]) -> int:
    """Cuantas cartas tendra la mano al rellenarse: todas sus posiciones menos las de unidades muertas."""
    return sum(1 for c in mano if c.tipo != TipoCarta.SUELO)


def _ficha(c: Carta, valores: dict) -> Ficha:
    ulti = c.tipo == TipoCarta.ULTI
    return Ficha(c.nombre, c.rango, ulti, c.jugable, valor_de(c.nombre, c.rango, ulti, valores))


def posiciones_reales(mano: list[Carta]) -> list[int]:
    """Posicion en pantalla de cada carta que cuenta para el plan (el plan las numera sin huecos)."""
    return [c.posicion for c in mano if c.tipo not in (TipoCarta.SUELO, TipoCarta.NINGUNA)]


# ----------------------------------------------------------- que cartas son la misma
def _dibujo(imagen: np.ndarray) -> np.ndarray:
    """El dibujo de la carta sin el marco (que cambia con el rango), normalizado: no le afecta el brillo."""
    alto, ancho = imagen.shape[:2]
    centro = imagen[int(alto * 0.15) : int(alto * 0.85), int(ancho * 0.15) : int(ancho * 0.85)]
    v = cv2.resize(centro, (9, 15), interpolation=cv2.INTER_AREA).astype(np.float32).ravel()
    v -= v.mean()
    return v / (np.linalg.norm(v) + 1e-6)


def agrupar_por_dibujo(mano: list[Carta], identificar=None) -> None:
    """Pone un nombre a las cartas sin nombre, igual para las que tienen el mismo dibujo: "dibujo_N" o,
    si ``identificar(carta)`` dice que carta es, "heroe.carta@N" (el @N evita que dos dibujos distintos
    tomados por la misma carta parezcan gemelos y el plan intente fusionarlos).
    Medido con las 1083 cartas de la base: la misma carta con otro brillo da < 0.5 y dos cartas
    distintas >= 26 (salvo versiones de color de un mismo heroe, que comparten dibujo)."""
    vistos: list[tuple[np.ndarray, str]] = []
    for c in mano:
        if c.nombre or c.imagen is None or c.tipo in (TipoCarta.SUELO, TipoCarta.NINGUNA, TipoCarta.ULTI):
            continue
        d = _dibujo(c.imagen)
        for otro, nombre in vistos:
            if 100 * (1 - float(d @ otro)) < MISMO_DIBUJO:
                c.nombre = nombre
                break
        else:
            n = len(vistos) + 1
            cual = identificar(c) if identificar else None
            c.nombre = f"{cual}@{n}" if cual else f"dibujo_{n}"
            vistos.append((d, c.nombre))

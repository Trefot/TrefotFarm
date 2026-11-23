"""Lectura de la mano de cartas: posicion, estado (normal, ulti, bloqueada, hueco), rango y huecos libres.

- Hueco vacio (carta recien jugada o unidad muerta): detector propio (lumen/huecos.py).
- Bloqueada: la carta se ve oscurecida (poco brillo).
- Rango: plantillas de bronce/plata/oro; sin rango = ulti.
Que carta ES (Odin single, Freyja ulti...) lo decide cada equipo con sus propias capturas (ver lumen/equipo.py).
"""

from dataclasses import dataclass, field
from enum import Enum

import cv2
import numpy as np

from lumen import huecos, juego
from lumen.vision import recortar


class TipoCarta(Enum):
    NORMAL = 0
    ULTI = 1
    BLOQUEADA = 9
    SUELO = 10  # hueco vacio (unidad muerta)
    NINGUNA = -100


# Una carta bloqueada lleva un velo OSCURO encima: lo mas claro de su dibujo no pasa de ~135. Se mide lo
# claro (percentil 90 del brillo del interior), no la media: con la media (umbral 90) se escapaban
# bloqueadas de dibujo claro (93, 96, 98, 100) y se tomaban por bloqueadas cartas normales de dibujo oscuro.
# Medido en 330 capturas de peleas (2026-10-28): bloqueadas 100-135; normales y ultis 220-255 casi todas
# (la ulti de Thonar, gris pero brillante, da 240+).
CLARO_BLOQUEADA = 150


class Rango(Enum):
    BRONCE = 0
    PLATA = 1
    ORO = 2
    NINGUNO = -100
    ULTI = 100


NO_JUGABLES = (TipoCarta.BLOQUEADA, TipoCarta.SUELO, TipoCarta.NINGUNA)


@dataclass
class Carta:
    posicion: int = -1  # 0 = la de mas a la izquierda
    rect: tuple[int, int, int, int] = (0, 0, 0, 0)  # x, y, w, h relativo a la ventana
    imagen: np.ndarray | None = field(default=None, repr=False)
    tipo: TipoCarta = TipoCarta.NINGUNA
    rango: Rango = Rango.NINGUNO
    nombre: str | None = None  # lo rellena el equipo si la reconoce

    @property
    def jugable(self) -> bool:
        return self.tipo not in NO_JUGABLES

    def __str__(self) -> str:
        return f"{self.posicion + 1}:{self.nombre or '?'}({self.tipo.name.lower()},{self.rango.name.lower()})"


def interior(carta: np.ndarray) -> np.ndarray:
    """La carta sin su marco (para medir si esta oscurecida)."""
    alto, ancho = carta.shape[:2]
    return carta[12 : alto - 20, 8 : ancho - 13]


def tipo_de(carta: np.ndarray) -> TipoCarta:
    if huecos.es_hueco(carta):
        return TipoCarta.SUELO
    dentro = interior(carta)
    if np.percentile(cv2.cvtColor(dentro, cv2.COLOR_BGR2HSV)[..., 2], 90) < CLARO_BLOQUEADA:
        return TipoCarta.BLOQUEADA
    return TipoCarta.NORMAL


def rango_de(carta: np.ndarray, tipo: TipoCarta) -> Rango:
    if tipo in (TipoCarta.SUELO, TipoCarta.NINGUNA):
        return Rango.NINGUNO
    if juego.rango_bronce.esta(carta, 0.7):
        return Rango.BRONCE
    if juego.rango_plata.esta(carta, 0.7):
        return Rango.PLATA
    if juego.rango_oro.esta(carta, 0.7):
        return Rango.ORO
    return Rango.ULTI  # las ultis no tienen estrellas de rango


# ---------------------------------------------------------------------- mano
def leer_mano(pantalla: np.ndarray, region: str = "mano_4", n: int = 8) -> list[Carta]:
    """Las cartas de la mano, de izquierda a derecha (8 con 4 unidades; en demonios, region
    "mano_demonio" y 7)."""
    x1, y1, _, _ = juego.REGION[region]
    mano = recortar(pantalla, juego.REGION[region])
    alto, ancho = mano.shape[:2]
    col = ancho // n
    cartas = []
    for i in range(n):
        vista = mano[:, i * col : (i + 1) * col]
        imagen = vista.copy()
        tipo = tipo_de(imagen)
        rango = rango_de(vista, tipo)  # sin copiar: asi la estrella se puede recortar como imagen propia (propias.py)
        if tipo == TipoCarta.NORMAL and rango == Rango.ULTI:
            tipo = TipoCarta.ULTI
        cartas.append(Carta(posicion=i, rect=(x1 + i * col, y1, col, alto), imagen=imagen, tipo=tipo, rango=rango))
    return cartas


def leer_mano_demonio(pantalla: np.ndarray) -> list[Carta]:
    return leer_mano(pantalla, "mano_demonio", 7)


def casillas_libres_demonio(pantalla: np.ndarray) -> int:
    """Cartas que faltan por jugar en este turno de demonio (0 = turno del demonio o animacion)."""
    return len(juego.casilla_vacia_demonio.buscar_todas(recortar(pantalla, juego.REGION["casillas_demonio"]), 0.8))


def contar_huecos(pantalla: np.ndarray, umbral: float = 0.8) -> int:
    """Cuantos huecos libres quedan en la barra de cartas del turno (0 = turno enemigo o terminado)."""
    if juego.mano_bloqueada.esta(pantalla, 0.6):
        return 4
    region = recortar(pantalla, juego.REGION["espacios_cartas"])
    return len(juego.espacio_vacio.buscar_todas(region, umbral))

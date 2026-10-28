"""Lectura de la mano de cartas: posicion, estado (normal, ulti, bloqueada, hueco), rango y huecos libres.

- Hueco vacio (unidad muerta): modelo entrenado de AutoFarming (assets/modelos), sigue funcionando.
- Bloqueada: la carta se ve oscurecida (poco brillo).
- Rango: plantillas de bronce/plata/oro; sin rango = ulti.
El modelo de "tipo de carta" de AutoFarming ya no sirve con el diseno actual de las cartas (dice
"ulti" para todas), asi que no se usa. Que carta ES (Odin single, Freyja ulti...) lo decide cada
equipo con sus propias capturas (ver lumen/equipo.py).
"""

import threading
from dataclasses import dataclass, field
from enum import Enum

import cv2
import dill
import numpy as np

from lumen import juego
from lumen.rutas import MODELOS
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


# ------------------------------------------------------------------- modelos
_modelos: dict[str, object] = {}
_lock_modelos = threading.Lock()


def _modelo(nombre: str):
    with _lock_modelos:
        if nombre not in _modelos:
            with (MODELOS / nombre).open("rb") as f:
                _modelos[nombre] = dill.load(f)
        return _modelos[nombre]


def _histogramas(imagen: np.ndarray, bins=(8, 8, 8)) -> np.ndarray:
    hsv = cv2.cvtColor(imagen, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, bins, [0, 180, 0, 256, 0, 256])
    cv2.normalize(hist, hist)
    return hist.flatten()


def _rasgos_suelo(imagen: np.ndarray) -> np.ndarray:
    hist = _histogramas(imagen)
    hist = np.sqrt(hist / hist.sum())
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    gris = cv2.resize(gris, (36, 91), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    textura = np.array(
        [gris.std(), np.abs(np.diff(gris, axis=0)).mean(), np.abs(np.diff(gris, axis=1)).mean(), gris.mean()],
        dtype=np.float32,
    ) * 10.0
    return np.concatenate([hist, textura])[np.newaxis, :]


def interior(carta: np.ndarray) -> np.ndarray:
    """La carta sin su marco (mismo recorte que usaron los modelos al entrenarse)."""
    alto, ancho = carta.shape[:2]
    return carta[12 : alto - 20, 8 : ancho - 13]


def tipo_de(carta: np.ndarray) -> TipoCarta:
    dentro = interior(carta)
    if bool(_modelo("ground_cards_predictor.svc").predict(_rasgos_suelo(dentro)).item()):
        return TipoCarta.SUELO
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
        imagen = mano[:, i * col : (i + 1) * col].copy()
        tipo = tipo_de(imagen)
        rango = rango_de(imagen, tipo)
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

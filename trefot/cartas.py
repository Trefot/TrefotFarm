"""Lectura de la mano de cartas: posicion, tipo (ataque, buff...), rango y huecos libres.

El tipo se predice con los dos modelos entrenados del proyecto original (assets/modelos);
el rango y los huecos con plantillas. Que carta ES (Odin single, Freyja ulti...) lo decide
cada equipo con sus propias capturas (ver trefot/equipo.py).
"""

import threading
from dataclasses import dataclass, field
from enum import Enum

import cv2
import dill
import numpy as np

from trefot import juego
from trefot.rutas import MODELOS
from trefot.vision import recortar


class TipoCarta(Enum):
    ATAQUE = 0
    POSTURA = 1
    CURACION = 2
    ATAQUE_DEBUFF = 3
    DEBUFF = 4
    BUFF = 5
    ULTI = -1
    BLOQUEADA = 9
    SUELO = 10  # hueco vacio (unidad muerta)
    NINGUNA = -100


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


def _rasgos_tipo(imagen: np.ndarray, rejilla=(4, 4)) -> np.ndarray:
    bloques = [
        bloque.mean(axis=(0, 1))
        for fila in np.array_split(imagen, rejilla[0], axis=0)
        for bloque in np.array_split(fila, rejilla[1], axis=1)
    ]
    return (np.asarray(bloques, dtype=np.float32).flatten() / 255.0)[np.newaxis, :]


def interior(carta: np.ndarray) -> np.ndarray:
    """La carta sin su marco (mismo recorte que usaron los modelos al entrenarse)."""
    alto, ancho = carta.shape[:2]
    return carta[12 : alto - 20, 8 : ancho - 13]


def tipo_de(carta: np.ndarray) -> TipoCarta:
    if bool(_modelo("ground_cards_predictor.svc").predict(_rasgos_suelo(interior(carta))).item()):
        return TipoCarta.SUELO
    icono = carta[0:20, 40:]  # esquina superior derecha: el icono del tipo de carta
    valor = _modelo("card_type_predictor.svm").predict(_rasgos_tipo(icono)).item()
    tipo = {0: TipoCarta.ATAQUE, 1: TipoCarta.POSTURA, 2: TipoCarta.CURACION, 3: TipoCarta.ATAQUE_DEBUFF,
            4: TipoCarta.DEBUFF, 5: TipoCarta.BUFF, -1: TipoCarta.ULTI, 9: TipoCarta.BLOQUEADA}.get(valor)
    # El modelo de tipos no sabe de "suelo"; si lo dice, en realidad es una ulti.
    return tipo or TipoCarta.ULTI


def rango_de(carta: np.ndarray, tipo: TipoCarta) -> Rango:
    if juego.rango_bronce.esta(carta, 0.7):
        return Rango.BRONCE
    if juego.rango_plata.esta(carta, 0.7):
        return Rango.PLATA
    if juego.rango_oro.esta(carta, 0.7):
        return Rango.ORO
    return Rango.ULTI if tipo == TipoCarta.ULTI else Rango.NINGUNO


# ---------------------------------------------------------------------- mano
def leer_mano(pantalla: np.ndarray) -> list[Carta]:
    """Las 8 cartas de la mano (4 unidades), de izquierda a derecha."""
    x1, y1, _, _ = juego.REGION["mano_4"]
    mano = recortar(pantalla, juego.REGION["mano_4"])
    alto, ancho = mano.shape[:2]
    col = ancho // 8
    cartas = []
    for i in range(8):
        imagen = mano[:, i * col : (i + 1) * col].copy()
        tipo = tipo_de(imagen)
        cartas.append(
            Carta(posicion=i, rect=(x1 + i * col, y1, col, alto), imagen=imagen, tipo=tipo, rango=rango_de(imagen, tipo))
        )
    return cartas


def contar_huecos(pantalla: np.ndarray, umbral: float = 0.8) -> int:
    """Cuantos huecos libres quedan en la barra de cartas del turno (0 = turno enemigo o terminado)."""
    if juego.mano_bloqueada.esta(pantalla, 0.6):
        return 4
    region = recortar(pantalla, juego.REGION["espacios_cartas"])
    return len(juego.espacio_vacio.buscar_todas(region, umbral))

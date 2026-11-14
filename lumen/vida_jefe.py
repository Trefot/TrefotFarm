"""Vida del jefe de una bestia: la barra de arriba, al lado de su cara.

Medido en un video del usuario (ciervo Floor 4, 2026-11-13): la vida son barras apiladas, una por fase, de colores
verde, azul, morado y rojo. La de la fase actual tapa a la siguiente y se vacia de derecha a izquierda; la ultima se
vacia sobre negro. Asi que se lee el color que hay a la izquierda (la capa de esta fase) y hasta donde llega.

``leer(p)`` -> Vida(capa, parte) o None si no se ve la barra (animaciones, pantallas negras, otra pantalla).
"""

from dataclasses import dataclass

import cv2
import numpy as np

BARRA = (88, 79, 318, 86)  # x1, y1, x2, y2 en la captura de siempre (550x940, con barra de titulo)
MARCO_FILAS = range(84, 91)  # la raya marron del marco, justo debajo de la barra (sin ella: no hay barra en pantalla)
CAPAS = {"verde": 67, "azul": 107, "morado": 149, "rojo": 166}  # tono (OpenCV, 0-180) de cada capa
TOLERANCIA_TONO = 9
VACIA = "vacia"


@dataclass(frozen=True)
class Vida:
    capa: str  # verde, azul, morado, rojo o "vacia"
    parte: float  # 0..1 de la capa que se ve (la vida que le queda a esta fase)

    @property
    def por_ciento(self) -> int:
        return round(self.parte * 100)

    def texto(self) -> str:
        return "barra vacía" if self.capa == VACIA else f"{self.capa} {self.por_ciento} %"


def _hay_marco(p) -> bool:
    """La raya marron bajo la barra (en el ciervo, con la luna detras, y en el pajaro, con el cielo oscuro)."""
    x1, _, x2, _ = BARRA
    marco = cv2.cvtColor(p[MARCO_FILAS.start:MARCO_FILAS.stop, x1:x2], cv2.COLOR_BGR2HSV).astype(int)
    for fila in marco:
        h, s, v = (float(np.median(fila[:, i])) for i in range(3))
        if 5 <= h <= 30 and s >= 60 and 45 <= v <= 150:
            return True
    return False


def _clases(p) -> np.ndarray | None:
    x1, y1, x2, y2 = BARRA
    if p is None or getattr(p, "ndim", 0) != 3 or p.shape[0] < MARCO_FILAS.stop or p.shape[1] < x2:
        return None
    if not _hay_marco(p):  # pantalla negra o sin barra
        return None
    hsv = cv2.cvtColor(p[y1:y2, x1:x2], cv2.COLOR_BGR2HSV).astype(int)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    clase = np.full(h.shape, -1)
    for i, tono in enumerate(CAPAS.values()):
        clase[(np.abs(h - tono) <= TOLERANCIA_TONO) & (s > 140) & (v > 55)] = i
    clase[v < 35] = len(CAPAS)  # negro: vacio
    columnas = []
    for x in range(clase.shape[1]):
        c = clase[:, x]
        c = c[c >= 0]
        columnas.append(int(np.bincount(c).argmax()) if len(c) >= 3 else -1)
    return np.array(columnas)


def leer(p) -> Vida | None:
    cols = _clases(p)
    if cols is None:
        return None
    inicio = cols[:12][cols[:12] >= 0]
    if len(inicio) < 6:
        return None
    capa = int(np.bincount(inicio).argmax())
    if capa == len(CAPAS):
        return Vida(VACIA, 0.0)
    hasta = 0
    for x, c in enumerate(cols):  # hasta donde llega la capa de arriba (las rayas de separacion no la cortan)
        if c == capa:
            hasta = x + 1
        elif c >= 0 and x - hasta > 3:
            break
    if (cols == capa).sum() < 0.5 * hasta:
        return None
    return Vida(list(CAPAS)[capa], hasta / len(cols))

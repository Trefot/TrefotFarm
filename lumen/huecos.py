"""Hueco vacio en la mano: la casilla donde no hay carta (se acaba de jugar, o la unidad murio).

Detector propio de Lumen (2026-11-22), en lugar del modelo antiguo. Se entreno con 3768 casillas
de la mano sacadas de las capturas del usuario (peleas de bestias, Indura, Monedas SA, menus), con
lumen/entrenar_huecos.py. Mira el color, la textura y la forma de la casilla y decide con una maquina de vectores de
soporte (SVM, nucleo RBF). Medido con pantallas de grupos que no vio al entrenar: 97,9 % igual que el modelo viejo en
peleas, y las diferencias eran casillas que no son cartas de la mano (menus, textos de ayuda, retratos del equipo).

Lo aprendido se guarda como numeros (assets/modelos/huecos_lumen.npz) y se calcula aqui con numpy: no hace falta
cargar ningun modelo de otra libreria.
"""

from __future__ import annotations

import threading

import cv2
import numpy as np

from lumen.rutas import MODELOS

ARCHIVO = MODELOS / "huecos_lumen.npz"
TAMANO = (32, 64)  # ancho, alto al que se reduce la casilla
_HOG = cv2.HOGDescriptor(TAMANO, (16, 16), (8, 8), (8, 8), 9)
_lock = threading.Lock()
_datos: dict | None = None


def rasgos(casilla: np.ndarray) -> np.ndarray:
    """Color (histograma HSV), forma (HOG) y textura de una casilla de la mano."""
    z = cv2.resize(casilla, TAMANO, interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(z, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1, 2], None, [8, 4, 4], [0, 180, 0, 256, 0, 256]).flatten()
    h = np.sqrt(h / max(float(h.sum()), 1.0))
    g = cv2.cvtColor(z, cv2.COLOR_BGR2GRAY)
    forma = _HOG.compute(g).flatten() * 0.5
    gf = g.astype(np.float32) / 255
    textura = np.array([gf.std(), np.abs(np.diff(gf, axis=0)).mean(), np.abs(np.diff(gf, axis=1)).mean(),
                        gf.mean()], dtype=np.float32) * 4
    return np.concatenate([h, forma, textura]).astype(np.float32)


def _cargar() -> dict:
    global _datos
    with _lock:
        if _datos is None:
            with np.load(ARCHIVO) as f:
                _datos = {k: f[k].astype(np.float32) for k in ("vectores", "pesos", "sesgo", "gamma")}
        return _datos


def puntaje(casilla: np.ndarray) -> float:
    """> 0: hueco vacio; < 0: hay carta. Es la decision de la SVM (suma de nucleos RBF con los vectores de soporte)."""
    d = _cargar()
    x = rasgos(casilla)
    dist = ((d["vectores"] - x) ** 2).sum(axis=1)
    return float(d["pesos"] @ np.exp(-float(d["gamma"]) * dist) + float(d["sesgo"]))


def es_hueco(casilla: np.ndarray) -> bool:
    return puntaje(casilla) > 0

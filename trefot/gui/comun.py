"""Piezas de interfaz que comparten varias paginas."""

import cv2
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from trefot import juego


def a_pixmap(imagen: np.ndarray, ancho: int | None = None) -> QPixmap:
    rgb = cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB)
    alto_px, ancho_px = rgb.shape[:2]
    qimg = QImage(rgb.data, ancho_px, alto_px, 3 * ancho_px, QImage.Format_RGB888).copy()
    pix = QPixmap.fromImage(qimg)
    return pix.scaledToWidth(ancho, Qt.SmoothTransformation) if ancho else pix


def dibujar_regiones(pantalla: np.ndarray) -> np.ndarray:
    img = pantalla.copy()
    for region in juego.REGION.values():
        cv2.rectangle(img, region[:2], region[2:], (38, 165, 224), 2)
    for punto in juego.COORD.values():
        cv2.circle(img, punto, 6, (97, 100, 239), 2)
    return img


def tarjeta(titulo: str, valor: str = "0") -> tuple[QFrame, QLabel]:
    """Recuadro con una cifra grande y su titulo."""
    marco = QFrame(objectName="tarjeta")
    capa = QVBoxLayout(marco)
    capa.setContentsMargins(12, 8, 12, 8)
    cifra = QLabel(valor, objectName="cifra")
    capa.addWidget(cifra)
    capa.addWidget(QLabel(titulo, objectName="tenue"))
    return marco, cifra


class Pagina(QWidget):
    """Pagina con titulo y subtitulo arriba. El contenido va en ``self.cuerpo``."""

    titulo = ""
    subtitulo = ""

    def __init__(self):
        super().__init__()
        capa = QVBoxLayout(self)
        capa.setContentsMargins(22, 16, 22, 16)
        cabecera = QHBoxLayout()
        textos = QVBoxLayout()
        textos.addWidget(QLabel(self.titulo, objectName="titulo_pagina"))
        if self.subtitulo:
            textos.addWidget(QLabel(self.subtitulo, objectName="tenue", wordWrap=True))
        cabecera.addLayout(textos, 1)
        self.acciones = QHBoxLayout()
        cabecera.addLayout(self.acciones)
        capa.addLayout(cabecera)
        self.cuerpo = QVBoxLayout()
        self.cuerpo.setSpacing(12)
        capa.addLayout(self.cuerpo, 1)

    def al_mostrar(self):
        """Se llama cada vez que el usuario entra a la pagina."""


def formatear_tiempo(segundos: float) -> str:
    s = int(max(0, segundos))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"

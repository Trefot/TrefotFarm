"""Piezas de interfaz que comparten varias paginas."""

import cv2
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget


def a_pixmap(imagen: np.ndarray, ancho: int | None = None) -> QPixmap:
    rgb = cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB)
    alto_px, ancho_px = rgb.shape[:2]
    qimg = QImage(rgb.data, ancho_px, alto_px, 3 * ancho_px, QImage.Format_RGB888).copy()
    pix = QPixmap.fromImage(qimg)
    return pix.scaledToWidth(ancho, Qt.SmoothTransformation) if ancho else pix


def tarjeta(titulo: str, valor: str = "0", icono: str | None = None) -> tuple[QFrame, QLabel]:
    """Recuadro con una cifra grande y su titulo (y un icono a la izquierda, si se da)."""
    from lumen.gui import iconos, tema

    marco = QFrame(objectName="tarjeta")
    fila = QHBoxLayout(marco)
    fila.setContentsMargins(14, 10, 14, 10)
    fila.setSpacing(12)
    if icono:
        dibujo = QLabel(objectName="icono_tarjeta")
        dibujo.setPixmap(iconos.pixmap(icono, 26, tema.ACENTO))
        dibujo.setFixedSize(44, 44)
        dibujo.setAlignment(Qt.AlignCenter)
        fila.addWidget(dibujo)
    capa = QVBoxLayout()
    capa.setSpacing(0)
    cifra = QLabel(valor, objectName="cifra")
    capa.addWidget(cifra)
    capa.addWidget(QLabel(titulo, objectName="tenue"))
    fila.addLayout(capa, 1)
    return marco, cifra


class Pagina(QWidget):
    """Pagina con titulo y subtitulo arriba. El contenido va en ``self.cuerpo``."""

    titulo = ""
    subtitulo = ""
    desplazable = False  # True: el cuerpo lleva barra de desplazamiento si no cabe

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
        if self.desplazable:
            contenido = QWidget(objectName="contenido_desplazable")
            contenido.setLayout(self.cuerpo)
            self.cuerpo.setContentsMargins(0, 0, 6, 0)
            area = QScrollArea(objectName="area_pagina", widgetResizable=True, frameShape=QFrame.NoFrame)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            area.setWidget(contenido)
            capa.addWidget(area, 1)
        else:
            capa.addLayout(self.cuerpo, 1)

    def al_mostrar(self):
        """Se llama cada vez que el usuario entra a la pagina."""


def formatear_tiempo(segundos: float) -> str:
    s = int(max(0, segundos))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def icono_premio(p, tam: int) -> QPixmap:
    """El icono del objeto con su cantidad (×5, ×2–5) en la esquina, como en el juego."""
    from lumen.gui import iconos, tema

    pix = QPixmap(str(p.icono))
    if pix.isNull():
        pix = iconos.pixmap("mdi6.help-box", tam, tema.TENUE)
    pix = pix.scaled(tam, tam, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    if p.texto_cantidad:
        pintor = QPainter(pix)
        pintor.setRenderHint(QPainter.Antialiasing)
        fuente = pintor.font()
        fuente.setBold(True)
        fuente.setPointSizeF(7.5)
        pintor.setFont(fuente)
        caja = pix.rect().adjusted(0, 0, -3, -1)
        pintor.setPen(QColor(0, 0, 0, 220))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            pintor.drawText(caja.translated(dx, dy), Qt.AlignRight | Qt.AlignBottom, p.texto_cantidad)
        pintor.setPen(QColor("white"))
        pintor.drawText(caja, Qt.AlignRight | Qt.AlignBottom, p.texto_cantidad)
        pintor.end()
    return pix

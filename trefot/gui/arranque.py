"""Pantalla de carga: el emblema, el nombre y una barra mientras se prepara la interfaz.

Se dibuja con los colores de la skin activa, asi en Halloween o Navidad tambien va vestida.
"""

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PyQt5.QtWidgets import QApplication, QSplashScreen

import trefot
from trefot.gui import iconos, tema
from trefot.rutas import ASSETS

ICONO = ASSETS / "icono" / "trefot.ico"
EMBLEMA = ASSETS / "icono" / "trefot_512.png"
ANCHO, ALTO = 560, 330


class PantallaCarga(QSplashScreen):
    def __init__(self):
        super().__init__(QPixmap(ANCHO, ALTO), Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.mensaje = "Preparando..."
        self.progreso = 0.0
        self.emblema = QPixmap(str(EMBLEMA)).scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.adorno = iconos.pixmap(tema.SKIN.icono, 22, tema.ACENTO) if tema.SKIN.icono else None
        self._pintar()

    def paso(self, mensaje: str, progreso: float):
        self.mensaje = mensaje
        self.progreso = max(0.0, min(1.0, progreso))
        self._pintar()
        QApplication.processEvents()

    def _pintar(self):
        s = tema.SKIN
        pix = QPixmap(ANCHO, ALTO)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        # fondo con marco dorado
        caja = QRectF(1.5, 1.5, ANCHO - 3, ALTO - 3)
        fondo = QLinearGradient(0, 0, 0, ALTO)
        fondo.setColorAt(0, QColor(s.panel_alto))
        fondo.setColorAt(1, QColor(s.lateral))
        camino = QPainterPath()
        camino.addRoundedRect(caja, 18, 18)
        p.fillPath(camino, fondo)
        p.setPen(QPen(QColor(s.borde_oro), 3))
        p.drawPath(camino)
        p.setPen(QPen(QColor(s.borde_oro), 1))
        p.drawRoundedRect(caja.adjusted(8, 8, -8, -8), 12, 12)

        # emblema y nombre
        p.drawPixmap(34, 60, self.emblema)
        p.setPen(QColor(s.acento))
        p.setFont(QFont(tema.FUENTE_MARCA, 30, QFont.Bold))
        p.drawText(QRectF(205, 70, ANCHO - 225, 60), Qt.AlignLeft | Qt.AlignVCenter, "Trefot Farm")
        p.setPen(QColor(s.tenue))
        lema = QFont(tema.FUENTE_TITULOS, 10)
        lema.setLetterSpacing(QFont.AbsoluteSpacing, 3)
        p.setFont(lema)
        p.drawText(QRectF(208, 128, ANCHO - 225, 24), Qt.AlignLeft | Qt.AlignVCenter, "AUTOFARMING · 7DS")
        if s.saludo:
            x = 208
            if self.adorno:
                p.drawPixmap(x, 168, self.adorno)
                x += 30
            p.setPen(QColor(s.acento_claro))
            p.setFont(QFont(tema.FUENTE_TITULOS, 11, QFont.Bold))
            p.drawText(QRectF(x, 164, ANCHO - x - 20, 30), Qt.AlignLeft | Qt.AlignVCenter, s.saludo)

        # barra de progreso y mensaje
        barra = QRectF(34, ALTO - 74, ANCHO - 68, 10)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(s.hundido))
        p.drawRoundedRect(barra, 5, 5)
        if self.progreso > 0:
            relleno = QLinearGradient(barra.left(), 0, barra.right(), 0)
            relleno.setColorAt(0, QColor(s.borde_oro))
            relleno.setColorAt(1, QColor(s.acento_claro))
            p.setBrush(relleno)
            p.drawRoundedRect(QRectF(barra.left(), barra.top(), barra.width() * self.progreso, barra.height()), 5, 5)
        p.setFont(QFont("Segoe UI", 9))
        p.setPen(QColor(s.texto))
        p.drawText(QRectF(34, ALTO - 56, ANCHO - 200, 24), Qt.AlignLeft | Qt.AlignVCenter, self.mensaje)
        p.setPen(QColor(s.tenue))
        p.drawText(QRectF(ANCHO - 200, ALTO - 56, 166, 24), Qt.AlignRight | Qt.AlignVCenter, f"v{trefot.__version__}")
        p.end()
        self.setPixmap(pix)

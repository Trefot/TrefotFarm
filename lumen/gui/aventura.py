"""Superficies ilustradas con luz y movimiento breve al pasar el cursor."""

from PyQt5.QtCore import QRectF, Qt, QVariantAnimation, QEasingCurve
from PyQt5.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PyQt5.QtWidgets import QFrame

from lumen.rutas import ASSETS


class PanelAventura(QFrame):
    def __init__(self, imagen=None, *, portada=False):
        super().__init__()
        self.setObjectName("escena_aventura" if portada else "aventura_card")
        self.portada = portada
        self.imagen = QPixmap(str(imagen)) if imagen else QPixmap()
        self.brillo = 0.0
        self.animacion = QVariantAnimation(self)
        self.animacion.setDuration(190)
        self.animacion.setEasingCurve(QEasingCurve.OutCubic)
        self.animacion.valueChanged.connect(self._luz)
        self.setAttribute(Qt.WA_Hover)
        self.setMinimumHeight(300 if portada else 190)

    def _luz(self, valor):
        self.brillo = float(valor)
        self.update()

    def _animar(self, valor):
        self.animacion.stop()
        self.animacion.setStartValue(self.brillo)
        self.animacion.setEndValue(valor)
        self.animacion.start()

    def enterEvent(self, evento):
        self._animar(1.0)
        super().enterEvent(evento)

    def leaveEvent(self, evento):
        self._animar(0.0)
        super().leaveEvent(evento)

    def paintEvent(self, evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        clip = QPainterPath()
        clip.addRoundedRect(rect, 15, 15)
        p.setClipPath(clip)
        fondo = QLinearGradient(0, 0, self.width(), self.height())
        fondo.setColorAt(0, QColor("#38261f"))
        fondo.setColorAt(1, QColor("#171311"))
        p.fillRect(rect, fondo)
        if not self.imagen.isNull():
            area = (
                rect
                if self.portada
                else QRectF(self.width() * 0.32, 0, self.width() * 0.68, self.height())
            )
            pix = self.imagen
            escala = max(area.width() / pix.width(), area.height() / pix.height()) * (
                1 + self.brillo * 0.035
            )
            w, h = pix.width() * escala, pix.height() * escala
            p.drawPixmap(
                QRectF(area.center().x() - w / 2, area.center().y() - h / 2, w, h),
                pix,
                QRectF(pix.rect()),
            )
        sombra = QLinearGradient(0, 0, self.width(), 0)
        sombra.setColorAt(0, QColor(22, 15, 13, 247))
        sombra.setColorAt(0.42, QColor(29, 18, 14, 224 if self.portada else 241))
        sombra.setColorAt(1, QColor(28, 14, 8, 20 if self.portada else 65))
        p.fillRect(rect, sombra)
        suelo = QLinearGradient(0, self.height() * 0.6, 0, self.height())
        suelo.setColorAt(0, QColor(20, 12, 9, 0))
        suelo.setColorAt(1, QColor(20, 12, 9, 160))
        p.fillRect(rect, suelo)
        p.setClipping(False)
        p.setPen(
            QPen(
                QColor(174 + int(50 * self.brillo), 128 + int(38 * self.brillo), 63),
                1.2,
            )
        )
        p.drawRoundedRect(rect, 15, 15)
        p.end()


def escena_taberna():
    return PanelAventura(ASSETS / "interfaz" / "taberna.png", portada=True)

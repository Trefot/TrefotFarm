"""Rueda para elegir que farmear: la foto del contenido elegido en grande y las vecinas a los lados.

Se gira con las flechas, con clic en una vecina, con la rueda del raton o con las teclas.
"""

from PyQt5.QtCore import QEasingCurve, QPointF, QRectF, QSize, Qt, QVariantAnimation, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PyQt5.QtWidgets import QPushButton, QWidget

from lumen.gui import iconos, tema

TAM = 200  # diametro de la foto del centro
SEPARACION = 175  # distancia entre el centro y la primera vecina


def foto_redonda(contenido, tam: int = TAM) -> QPixmap:
    """La foto del contenido en circulo; si no tiene, su icono dorado sobre fondo oscuro."""
    pix = iconos.redondo(contenido.foto, tam) if contenido.foto else None
    if pix:
        return pix
    pix = QPixmap(tam, tam)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    fondo = QRadialGradient(QPointF(tam / 2, tam / 2.6), tam * 0.6)
    fondo.setColorAt(0, QColor(tema.SKIN.panel_alto))
    fondo.setColorAt(1, QColor(tema.SKIN.profundo))
    p.setBrush(fondo)
    p.setPen(Qt.NoPen)
    p.drawEllipse(QRectF(1, 1, tam - 2, tam - 2))
    icono = iconos.pixmap(contenido.icono, int(tam * 0.5), tema.ACENTO)
    p.drawPixmap(int((tam - icono.width()) / 2), int((tam - icono.height()) / 2), icono)
    p.end()
    return pix


class Rueda(QWidget):
    cambiado = pyqtSignal(int)  # indice del contenido del centro

    def __init__(self, contenidos: list, listos: set[str], indice: int = 0):
        super().__init__()
        self.contenidos = contenidos
        self.listos = listos  # ids de contenidos con algun destino que ya funciona
        self.fotos = [foto_redonda(c) for c in contenidos]
        self.indice = indice
        self.posicion = float(indice)  # se mueve con la animacion
        self.setMinimumHeight(TAM + 40)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.animacion = QVariantAnimation(self, duration=260, easingCurve=QEasingCurve.OutCubic)
        self.animacion.valueChanged.connect(self._mover)
        self.flechas = []
        for paso, icono in ((-1, "mdi6.chevron-left"), (1, "mdi6.chevron-right")):
            b = QPushButton(self, objectName="flecha_rueda")
            b.setIcon(iconos.icono(icono, tema.ACENTO))
            b.setIconSize(QSize(30, 30))
            b.setFixedSize(46, 46)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _, s=paso: self.girar(s))
            self.flechas.append(b)

    # ------------------------------------------------------------------ girar
    def girar(self, pasos: int):
        self.ir_a((self.indice + pasos) % len(self.contenidos), pasos)

    def ir_a(self, indice: int, direccion: int = 0):
        if indice == self.indice:
            return
        n = len(self.contenidos)
        if not direccion:  # por el camino mas corto
            direccion = (indice - self.indice + n // 2) % n - n // 2
        destino = self.posicion + direccion
        self.indice = indice
        self.animacion.stop()
        self.animacion.setStartValue(self.posicion)
        self.animacion.setEndValue(destino)
        self.animacion.start()
        self.cambiado.emit(indice)

    def _mover(self, valor):
        self.posicion = float(valor)
        if self.animacion.state() != QVariantAnimation.Running or valor == self.animacion.endValue():
            self.posicion = float(self.indice)
        self.update()

    # ------------------------------------------------------------------ eventos
    def resizeEvent(self, evento):
        y = (self.height() - 46) // 2
        self.flechas[0].move(8, y)
        self.flechas[1].move(self.width() - 54, y)
        super().resizeEvent(evento)

    def mousePressEvent(self, evento):
        dx = evento.x() - self.width() / 2
        if abs(dx) > TAM / 2:
            self.girar(1 if dx > 0 else -1)
        self.setFocus()

    def wheelEvent(self, evento):
        self.girar(-1 if evento.angleDelta().y() > 0 else 1)

    def keyPressEvent(self, evento):
        if evento.key() in (Qt.Key_Left, Qt.Key_Right):
            self.girar(-1 if evento.key() == Qt.Key_Left else 1)
        else:
            super().keyPressEvent(evento)

    # ------------------------------------------------------------------ dibujo
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        n = len(self.contenidos)
        cx, cy = self.width() / 2, self.height() / 2
        visibles = []
        for i in range(n):
            d = (i - self.posicion + n / 2) % n - n / 2  # distancia con signo, dando la vuelta
            if abs(d) <= 2.6:
                visibles.append((abs(d), d, i))
        # luz detras de la del centro
        halo = QRadialGradient(QPointF(cx, cy), TAM * 0.85)
        luz = QColor(tema.ACENTO)
        luz.setAlpha(70)
        halo.setColorAt(0, luz)
        halo.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(halo)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), TAM * 0.85, TAM * 0.85)
        for distancia, d, i in sorted(visibles, reverse=True):  # las lejanas primero
            escala = max(0.38, 1 - 0.36 * distancia)
            tam = TAM * escala
            x = cx + d * SEPARACION * (1 - 0.13 * min(distancia, 2))
            rect = QRectF(x - tam / 2, cy - tam / 2, tam, tam)
            listo = self.contenidos[i].id in self.listos
            p.setOpacity(max(0.0, 1 - 0.38 * distancia) * (1 if listo or distancia < 0.5 else 0.75))
            p.drawPixmap(rect.toRect(), self.fotos[i])
            if not listo:  # velo oscuro: aun no se puede farmear
                velo = QPainterPath()
                velo.addEllipse(rect)
                p.fillPath(velo, QColor(0, 0, 0, 90))
            p.setOpacity(1)
            borde = QColor(tema.ACENTO if distancia < 0.5 else tema.SKIN.borde_oro)
            p.setPen(QPen(borde, 3.5 if distancia < 0.5 else 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(rect.adjusted(1, 1, -1, -1))
            if not listo and distancia < 0.5:
                candado = iconos.pixmap("candado", 30, tema.TEXTO)
                fondo = QRectF(rect.right() - 46, rect.bottom() - 46, 40, 40)
                p.setPen(QPen(QColor(tema.SKIN.borde_oro), 1.5))
                p.setBrush(QColor(tema.SKIN.profundo))
                p.drawEllipse(fondo)
                p.drawPixmap(int(fondo.x() + 5), int(fondo.y() + 5), candado)
        p.end()

"""Pagina Historial: todas las sesiones de farmeo y sus totales."""

import time

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QPainter
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from lumen import historial
from lumen.gui import iconos, tema
from lumen.gui.comun import Pagina, formatear_tiempo, tarjeta

COLUMNAS = ["Fecha", "Modo", "Duración", "Victorias", "Derrotas", "Reinicios", "% éxito", "Pociones", "Versión"]
DIAS_GRAFICO = 14


def victorias_por_dia(sesiones: list[dict], dias: int = DIAS_GRAFICO) -> list[tuple[str, int]]:
    """[(etiqueta, victorias)] de los ultimos `dias` dias, el mas antiguo primero."""
    hoy = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
    cuentas = [0] * dias
    for s in sesiones:
        atras = int(-((s.get("inicio", 0) - hoy) // 86400))  # 0 = hoy, 1 = ayer...
        if 0 <= atras < dias:
            cuentas[dias - 1 - atras] += int(s.get("victorias", 0))
    etiquetas = [time.strftime("%d/%m", time.localtime(hoy - 86400 * (dias - 1 - i) + 3600)) for i in range(dias)]
    return list(zip(etiquetas, cuentas))


class GraficoBarras(QWidget):
    """Barras doradas sencillas: victorias de cada dia."""

    def __init__(self):
        super().__init__()
        self.datos: list[tuple[str, int]] = []
        self.setMinimumHeight(170)

    def poner(self, datos):
        self.datos = datos
        self.update()

    def paintEvent(self, _evento):
        if not self.datos:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        ancho, alto = self.width(), self.height()
        abajo, arriba = 22, 18
        maximo = max(1, max(v for _, v in self.datos))
        hueco = ancho / len(self.datos)
        letra = QFont(self.font())
        letra.setPointSizeF(8)
        p.setFont(letra)
        p.setPen(QColor(tema.BORDE))
        p.drawLine(0, alto - abajo, ancho, alto - abajo)
        for i, (etiqueta, valor) in enumerate(self.datos):
            x = i * hueco + hueco * 0.2
            barra = hueco * 0.6
            h = (alto - abajo - arriba) * valor / maximo
            rect = QRectF(x, alto - abajo - h, barra, h)
            es_hoy = i == len(self.datos) - 1
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(tema.ACENTO if valor else tema.BORDE))
            if not es_hoy and valor:
                p.setOpacity(0.75)
            p.drawRoundedRect(rect, 3, 3)
            p.setOpacity(1)
            p.setPen(QColor(tema.TEXTO if valor else tema.TENUE))
            if valor:
                p.drawText(QRectF(i * hueco, alto - abajo - h - 16, hueco, 14), Qt.AlignCenter, str(valor))
            p.setPen(QColor(tema.ACENTO if es_hoy else tema.TENUE))
            p.drawText(QRectF(i * hueco, alto - abajo + 4, hueco, 14), Qt.AlignCenter, "Hoy" if es_hoy else etiqueta)
        p.end()


class PaginaHistorial(Pagina):
    titulo = "Historial"
    subtitulo = "Cada sesión de farmeo queda guardada aquí, con sus victorias y su tiempo."

    def __init__(self, app):
        super().__init__()
        b = QPushButton(" Actualizar", objectName="chico")
        b.setIcon(iconos.icono("actualizar", tema.TEXTO))
        b.clicked.connect(self.al_mostrar)
        self.acciones.addWidget(b)

        fila = QHBoxLayout()
        self.cifras = {}
        for clave, titulo, ic in (("victorias", "Victorias totales", "trofeo"), ("tasa", "% de éxito", "tasa"),
                                  ("por_hora", "Victorias por hora", "rayo"), ("tiempo", "Tiempo farmeando", "reloj"),
                                  ("sesiones", "Sesiones", "sesiones")):
            marco, cifra = tarjeta(titulo, icono=ic)
            self.cifras[clave] = cifra
            fila.addWidget(marco)
        self.cuerpo.addLayout(fila)

        caja = QFrame(objectName="seccion")
        capa_caja = QVBoxLayout(caja)
        capa_caja.setContentsMargins(16, 12, 16, 10)
        capa_caja.addWidget(QLabel(f"Victorias de los últimos {DIAS_GRAFICO} días", objectName="titulo_seccion"))
        self.grafico = GraficoBarras()
        capa_caja.addWidget(self.grafico)
        self.cuerpo.addWidget(caja)
        self.cuerpo.addWidget(QLabel("Sesiones", objectName="titulo_seccion"))

        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(34)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.cuerpo.addWidget(self.tabla, 1)
        self.al_mostrar()

    def al_mostrar(self):
        sesiones = historial.leer()
        t = historial.totales(sesiones)
        self.cifras["victorias"].setText(str(t["victorias"]))
        self.cifras["tasa"].setText(f"{t['tasa']:.0f}%")
        self.cifras["por_hora"].setText(f"{t['por_hora']:.1f}")
        self.cifras["tiempo"].setText(formatear_tiempo(t["segundos"]))
        self.cifras["sesiones"].setText(str(t["sesiones"]))
        self.grafico.poner(victorias_por_dia(sesiones))

        self.tabla.setRowCount(len(sesiones))
        for fila, s in enumerate(sesiones):
            peleas = s.get("victorias", 0) + s.get("derrotas", 0) + s.get("reinicios", 0)
            valores = [
                time.strftime("%d/%m/%Y %H:%M", time.localtime(s.get("inicio", 0))),
                s.get("nombre", s.get("modo", "?")),
                formatear_tiempo(s.get("fin", 0) - s.get("inicio", 0)),
                s.get("victorias", 0),
                s.get("derrotas", 0),
                s.get("reinicios", 0),
                f"{100 * s.get('victorias', 0) / peleas:.0f}%" if peleas else "—",
                s.get("pociones", 0),
                s.get("version", ""),
            ]
            for col, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor))
                item.setTextAlignment(Qt.AlignCenter)
                self.tabla.setItem(fila, col, item)

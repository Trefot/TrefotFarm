"""Pagina Historial: todas las sesiones de farmeo y sus totales."""

import time

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAbstractItemView, QHBoxLayout, QHeaderView, QPushButton, QTableWidget, QTableWidgetItem

from trefot import historial
from trefot.gui.comun import Pagina, formatear_tiempo, tarjeta

COLUMNAS = ["Fecha", "Modo", "Duracion", "Victorias", "Derrotas", "Reinicios", "% exito", "Pociones", "Version"]


class PaginaHistorial(Pagina):
    titulo = "Historial"
    subtitulo = "Cada sesion de farmeo queda guardada aqui (logs/historial.jsonl)."

    def __init__(self, app):
        super().__init__()
        b = QPushButton("Actualizar")
        b.clicked.connect(self.al_mostrar)
        self.acciones.addWidget(b)

        fila = QHBoxLayout()
        self.cifras = {}
        for clave, titulo in (("victorias", "Victorias totales"), ("tasa", "% exito"),
                              ("por_hora", "Victorias por hora"), ("tiempo", "Tiempo farmeando"), ("sesiones", "Sesiones")):
            marco, cifra = tarjeta(titulo)
            self.cifras[clave] = cifra
            fila.addWidget(marco)
        self.cuerpo.addLayout(fila)

        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        self.tabla.verticalHeader().setVisible(False)
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

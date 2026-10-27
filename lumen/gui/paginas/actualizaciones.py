"""Pantalla de bloqueo cuando hay una actualizacion obligatoria."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget

from lumen.control import control


class PantallaBloqueo(QWidget):
    """Ocupa toda la ventana mientras haya una actualizacion obligatoria pendiente."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        capa = QVBoxLayout(self)
        capa.setAlignment(Qt.AlignCenter)
        caja = QFrame(objectName="tarjeta")
        caja.setMaximumWidth(620)
        interior = QVBoxLayout(caja)
        interior.setContentsMargins(30, 26, 30, 26)
        interior.setSpacing(12)
        interior.addWidget(QLabel("⟳", objectName="cifra_grande", alignment=Qt.AlignCenter))
        interior.addWidget(QLabel("Actualizacion obligatoria", objectName="titulo_pagina", alignment=Qt.AlignCenter))
        self.versiones = QLabel(objectName="tenue", alignment=Qt.AlignCenter)
        interior.addWidget(self.versiones)
        interior.addWidget(QLabel("Novedades:"))
        self.lista = QListWidget()
        self.lista.setMaximumHeight(170)
        interior.addWidget(self.lista)
        self.progreso = QLabel(objectName="tenue", alignment=Qt.AlignCenter, wordWrap=True)
        interior.addWidget(self.progreso)
        self.boton = QPushButton("Actualizar ahora", objectName="primario")
        self.boton.setMinimumHeight(46)
        self.boton.clicked.connect(app.aplicar_update)
        interior.addWidget(self.boton)
        self.b_detener = QPushButton("Detener el bot ya (sin esperar a que acabe la pelea)", objectName="detener")
        self.b_detener.clicked.connect(lambda: control.detener())
        interior.addWidget(self.b_detener)
        interior.addWidget(QLabel("Tus capturas, ajustes e historial se conservan.", objectName="tenue", alignment=Qt.AlignCenter))
        capa.addWidget(caja)

    def refrescar(self):
        est = self.app.estado_update
        if est:
            self.versiones.setText(f"v{est.version_local}  →  v{est.version_remota}")
            self.lista.clear()
            self.lista.addItems(est.cambios or ["(sin descripcion)"])
        self.b_detener.setVisible(self.app.puente.corriendo)
        if self.app.puente.corriendo:
            self.boton.setEnabled(False)
            self.progreso.setText("El bot terminara la pelea actual y se detendra; luego podras actualizar.")
        elif not self.app.actualizando:
            self.boton.setEnabled(True)
            self.progreso.setText("")

    def mensaje(self, texto: str):
        self.progreso.setText(texto)

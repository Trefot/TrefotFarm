"""Pagina Actualizaciones y pantalla de bloqueo cuando hay una actualizacion obligatoria."""

import time

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFormLayout, QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton, QVBoxLayout, QWidget

from trefot import actualizador
from trefot.control import control
from trefot.gui.comun import Pagina


class PaginaActualizaciones(Pagina):
    titulo = "Actualizaciones"
    subtitulo = "Las actualizaciones son obligatorias: cuando hay una nueva, el programa se bloquea hasta instalarla."

    def __init__(self, app):
        super().__init__()
        self.app = app

        estado = QGroupBox("Estado")
        f = QFormLayout(estado)
        self.lbl_version = QLabel()
        self.lbl_remoto = QLabel(wordWrap=True)
        self.lbl_revisado = QLabel()
        self.lbl_estado = QLabel(wordWrap=True)
        f.addRow("Version instalada", self.lbl_version)
        f.addRow("Repositorio", self.lbl_remoto)
        f.addRow("Ultima revision", self.lbl_revisado)
        f.addRow("Estado", self.lbl_estado)
        botones = QHBoxLayout()
        self.b_buscar = QPushButton("Buscar actualizaciones")
        self.b_buscar.clicked.connect(lambda: app.buscar_updates(manual=True))
        self.b_actualizar = QPushButton("⟳  Actualizar", objectName="primario")
        self.b_actualizar.clicked.connect(app.mostrar_bloqueo)
        botones.addWidget(self.b_buscar)
        botones.addWidget(self.b_actualizar)
        botones.addStretch()
        f.addRow(botones)
        self.cuerpo.addWidget(estado)

        self.grupo_cambios = QGroupBox("Cambios pendientes")
        capa = QVBoxLayout(self.grupo_cambios)
        self.lista = QListWidget()
        capa.addWidget(self.lista)
        self.cuerpo.addWidget(self.grupo_cambios)

        self.grupo_repo = QGroupBox("Conectar con GitHub")
        capa_repo = QVBoxLayout(self.grupo_repo)
        capa_repo.addWidget(QLabel(
            "Pega la URL de tu repositorio privado (p. ej. https://github.com/tu-usuario/TrefotFarm.git). "
            "La primera vez Windows te pedira iniciar sesion en GitHub.", objectName="tenue", wordWrap=True))
        fila = QHBoxLayout()
        self.url = QLineEdit(placeholderText="https://github.com/usuario/TrefotFarm.git")
        b = QPushButton("Guardar")
        b.clicked.connect(self._guardar_url)
        fila.addWidget(self.url, 1)
        fila.addWidget(b)
        capa_repo.addLayout(fila)
        self.cuerpo.addWidget(self.grupo_repo)
        self.cuerpo.addStretch()

    def al_mostrar(self):
        self.refrescar()

    def _guardar_url(self):
        try:
            actualizador.configurar_remoto(self.url.text())
        except actualizador.ErrorActualizacion as e:
            self.lbl_estado.setText(str(e))
            return
        self.app.buscar_updates(manual=True)

    def refrescar(self):
        est = self.app.estado_update
        remoto = actualizador.url_remota()
        self.lbl_version.setText(f"v{actualizador.version_local()}")
        self.lbl_remoto.setText(remoto or "sin configurar")
        self.url.setText(remoto)
        self.lbl_revisado.setText(time.strftime("%H:%M:%S", time.localtime(est.revisado)) if est else "—")
        if est is None:
            self.lbl_estado.setText("Buscando...")
        elif est.hay_update:
            self.lbl_estado.setText(f"Hay una actualizacion obligatoria: v{est.version_remota}")
        elif est.error:
            self.lbl_estado.setText(est.error)
        else:
            self.lbl_estado.setText("Estas al dia.")
        self.b_actualizar.setEnabled(bool(est and est.hay_update))
        self.lista.clear()
        self.lista.addItems((est.cambios if est else []) or ["(ninguno)"])
        self.grupo_cambios.setVisible(bool(est and est.hay_update))


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

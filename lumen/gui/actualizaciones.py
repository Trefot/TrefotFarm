"""Acceso visible a las actualizaciones y a los errores de conexion."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from lumen.gui import iconos, tema


class PanelActualizaciones(QFrame):
    def __init__(self, app):
        super().__init__(objectName="seccion")
        self.app = app
        fila = QHBoxLayout(self)
        fila.setContentsMargins(16, 12, 16, 12)
        textos = QVBoxLayout()
        textos.setSpacing(4)
        self.version = QLabel(
            f"Actualizaciones · v{app.version_cargada}", objectName="titulo_seccion"
        )
        self.estado = QLabel(objectName="tenue", wordWrap=True)
        self.estado.setTextFormat(Qt.PlainText)
        textos.addWidget(self.version)
        textos.addWidget(self.estado)
        fila.addLayout(textos, 1)
        self.boton = QPushButton("Buscar actualizaciones", objectName="primario")
        self.boton.setIcon(iconos.icono("actualizar", tema.SOBRE_ACENTO))
        self.boton.setMinimumWidth(228)
        self.boton.setAccessibleName("Buscar actualizaciones")
        self.boton.clicked.connect(self._accion)
        fila.addWidget(self.boton)
        self.refrescar()

    def _accion(self):
        estado = self.app.estado_update
        if self.app.reinicio_pendiente or (estado and estado.hay_update):
            self.app.accion_actualizar()
        else:
            self.app.buscar_updates(manual=True)

    def refrescar(self):
        estado = self.app.estado_update
        self.boton.setEnabled(not self.app.revisando and not self.app.actualizando)
        if self.app.actualizando:
            texto, mensaje = (
                "Actualizando…",
                "Descargando e instalando la actualización.",
            )
        elif self.app.revisando:
            texto, mensaje = (
                "Buscando…",
                "Comprobando las versiones disponibles en GitHub.",
            )
        elif self.app.reinicio_pendiente:
            texto, mensaje = (
                "Reiniciar app",
                "La actualización está instalada. Reinicia para cargarla.",
            )
        elif estado and estado.hay_update:
            texto, mensaje = (
                "Actualizar app",
                f"Nueva versión disponible: {estado.version_remota}.",
            )
        elif estado and estado.error:
            texto, mensaje = (
                "Reintentar búsqueda",
                f"No se pudo comprobar: {estado.error}",
            )
        elif estado:
            texto, mensaje = "Buscar actualizaciones", "Tu app está al día."
        else:
            texto, mensaje = (
                "Buscar actualizaciones",
                "Se comprueban automáticamente al abrir la app.",
            )
        self.boton.setText(texto)
        self.boton.setAccessibleName(texto)
        self.estado.setText(mensaje)

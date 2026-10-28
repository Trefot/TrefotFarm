"""Pagina Ayuda: guia con capturas del juego, problemas frecuentes y glosario.

El contenido esta en lumen/datos/ayuda.yaml y las imagenes en assets/ayuda.
"""

from pathlib import Path

import yaml
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from lumen.gui import iconos, tema
from lumen.gui.comun import Pagina
from lumen.rutas import ASSETS

CONTENIDO = Path(__file__).resolve().parents[2] / "datos" / "ayuda.yaml"
IMAGENES_AYUDA = ASSETS / "ayuda"
ANCHO_IMAGEN = 240
TIPOS = {"juego": "Del juego", "bot": "Del bot"}


def cargar() -> dict:
    with CONTENIDO.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _texto(html: str, nombre: str | None = None) -> QLabel:
    etiqueta = QLabel(html, wordWrap=True)
    etiqueta.setTextFormat(Qt.RichText)
    if nombre:
        etiqueta.setObjectName(nombre)
    return etiqueta


def _imagen(nombre: str, ancho: int = ANCHO_IMAGEN) -> QLabel | None:
    pix = QPixmap(str(IMAGENES_AYUDA / nombre))
    if pix.isNull():
        return None
    etiqueta = QLabel(objectName="foto_objeto")
    etiqueta.setPixmap(pix.scaledToWidth(ancho, Qt.SmoothTransformation))
    etiqueta.setFixedWidth(ancho + 4)
    etiqueta.setAlignment(Qt.AlignCenter)
    return etiqueta


def _desplazable(contenido: QWidget) -> QScrollArea:
    zona = QScrollArea(widgetResizable=True)
    zona.setWidget(contenido)
    return zona


class Desplegable(QFrame):
    """Pregunta que se abre al hacer clic y muestra su respuesta (y una imagen, si tiene)."""

    def __init__(self, pregunta: str, respuesta: str, imagen: str | None = None):
        super().__init__(objectName="tarjeta_equipo")
        capa = QVBoxLayout(self)
        capa.setContentsMargins(14, 8, 14, 8)
        self.boton = QPushButton(f"  {pregunta}", objectName="desplegable", checkable=True)
        self.boton.setCursor(Qt.PointingHandCursor)
        self.boton.toggled.connect(self._abrir)
        capa.addWidget(self.boton)
        self.cuerpo = QWidget(objectName="cuerpo_desplegable")
        fila = QHBoxLayout(self.cuerpo)
        fila.setContentsMargins(30, 0, 0, 8)
        fila.setSpacing(16)
        fila.addWidget(_texto(respuesta), 1, Qt.AlignTop)
        foto = _imagen(imagen, 170) if imagen else None
        if foto:
            fila.addWidget(foto, 0, Qt.AlignTop)
        capa.addWidget(self.cuerpo)
        self._abrir(False)

    def _abrir(self, abierto: bool):
        self.cuerpo.setVisible(abierto)
        self.boton.setIcon(iconos.icono("mdi6.chevron-down" if abierto else "mdi6.chevron-right", tema.ACENTO))


class PaginaAyuda(Pagina):
    titulo = "Ayuda"

    def __init__(self, app):
        super().__init__()
        self.app = app
        b_asistente = QPushButton(" Asistente de primera vez", objectName="chico")
        b_asistente.setIcon(iconos.icono("ayuda", tema.TEXTO))
        b_asistente.clicked.connect(app.abrir_asistente)
        self.acciones.addWidget(b_asistente)

        datos = cargar()
        self.pestanas = QTabWidget()
        self.pestanas.addTab(self._uso(datos.get("uso", [])), iconos.icono("mdi6.compass-outline", tema.TENUE), " Cómo usarlo  ")
        self.pestanas.addTab(self._guia(datos.get("guia", [])), iconos.icono("mdi6.book-open-variant", tema.TENUE), " Guía Floor 4")
        self.pestanas.addTab(self._problemas(datos.get("problemas", [])), iconos.icono("mdi6.lifebuoy", tema.TENUE), " Problemas")
        self.terminos = datos.get("glosario", [])
        self.pestanas.addTab(self._glosario(), iconos.icono("mdi6.book-alphabet", tema.TENUE), " Glosario")
        self.cuerpo.addWidget(self.pestanas, 1)

    # ------------------------------------------------------------- como usarlo
    def _uso(self, tarjetas: list[dict]) -> QWidget:
        """Una tarjeta corta por cada parte del bot, en dos columnas."""
        w = QWidget()
        capa = QVBoxLayout(w)
        capa.setContentsMargins(14, 14, 14, 14)
        rejilla = QGridLayout()
        rejilla.setSpacing(12)
        for i, t in enumerate(tarjetas):
            caja = QFrame(objectName="seccion")
            fila = QHBoxLayout(caja)
            fila.setContentsMargins(14, 12, 14, 12)
            fila.setSpacing(12)
            dibujo = QLabel(objectName="icono_tarjeta", alignment=Qt.AlignCenter)
            dibujo.setPixmap(iconos.pixmap(t.get("icono", "ayuda"), 24, tema.ACENTO))
            dibujo.setFixedSize(44, 44)
            fila.addWidget(dibujo, 0, Qt.AlignTop)
            textos = QVBoxLayout()
            textos.setSpacing(4)
            textos.addWidget(QLabel(t["titulo"], objectName="titulo_seccion"))
            textos.addWidget(_texto(t["texto"]))
            textos.addStretch()
            fila.addLayout(textos, 1)
            rejilla.addWidget(caja, i // 2, i % 2)
        rejilla.setColumnStretch(0, 1)
        rejilla.setColumnStretch(1, 1)
        capa.addLayout(rejilla)
        capa.addStretch()
        return _desplazable(w)

    # ------------------------------------------------------------------ guia
    def _guia(self, pasos: list[dict]) -> QWidget:
        w = QWidget()
        capa = QVBoxLayout(w)
        capa.setContentsMargins(14, 14, 14, 14)
        capa.setSpacing(12)
        capa.addWidget(_texto("Así farmea el bot <b>Skollandhati &amp; Hati · Floor 4</b>, paso a paso, con capturas "
                              "del juego.", "tenue"))
        for paso in pasos:
            caja = QFrame(objectName="seccion")
            fila = QHBoxLayout(caja)
            fila.setContentsMargins(16, 14, 16, 14)
            fila.setSpacing(18)
            foto = _imagen(paso["imagen"]) if paso.get("imagen") else None
            if foto:
                fila.addWidget(foto, 0, Qt.AlignTop)
            textos = QVBoxLayout()
            textos.setSpacing(6)
            textos.addWidget(QLabel(paso["titulo"], objectName="titulo_tarjeta"))
            textos.addWidget(_texto(paso["texto"]))
            textos.addStretch()
            fila.addLayout(textos, 1)
            capa.addWidget(caja)
        capa.addStretch()
        return _desplazable(w)

    # ------------------------------------------------------------- problemas
    def _problemas(self, lista: list[dict]) -> QWidget:
        w = QWidget()
        capa = QVBoxLayout(w)
        capa.setContentsMargins(14, 14, 14, 14)
        capa.setSpacing(8)
        capa.addWidget(_texto("Haz clic en una pregunta para ver la respuesta.", "tenue"))
        for p in lista:
            capa.addWidget(Desplegable(p["pregunta"], p["respuesta"], p.get("imagen")))
        capa.addStretch()
        return _desplazable(w)

    # --------------------------------------------------------------- glosario
    def _glosario(self) -> QWidget:
        w = QWidget()
        capa = QVBoxLayout(w)
        capa.setContentsMargins(14, 14, 14, 14)
        barra = QHBoxLayout()
        self.buscar = QLineEdit(placeholderText="Buscar una palabra...")
        self.buscar.setClearButtonEnabled(True)
        self.buscar.setMaximumWidth(300)
        self.buscar.textChanged.connect(self._pintar_glosario)
        barra.addWidget(self.buscar)
        self.filtro = QButtonGroup(self, exclusive=True)
        for i, (clave, texto) in enumerate([("", "Todas"), *TIPOS.items()]):
            b = QPushButton(texto, objectName="chip", checkable=True)
            b.setProperty("tipo", clave)
            b.setChecked(i == 0)
            self.filtro.addButton(b, i)
            barra.addWidget(b)
        self.filtro.buttonClicked.connect(lambda _: self._pintar_glosario())
        barra.addStretch()
        capa.addLayout(barra)
        self.lista_glosario = QVBoxLayout()
        self.lista_glosario.setSpacing(8)
        contenido = QWidget()
        contenido.setLayout(self.lista_glosario)
        capa.addWidget(_desplazable(contenido), 1)
        self._pintar_glosario()
        return w

    def _pintar_glosario(self):
        while self.lista_glosario.count():
            item = self.lista_glosario.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        texto = self.buscar.text().strip().lower()
        tipo = self.filtro.checkedButton().property("tipo") if self.filtro.checkedButton() else ""
        terminos = sorted(self.terminos, key=lambda t: t["termino"].lower())
        visibles = [t for t in terminos if (not tipo or t.get("tipo") == tipo)
                    and (not texto or texto in t["termino"].lower() or texto in t["definicion"].lower())]
        for t in visibles:
            caja = QFrame(objectName="tarjeta_equipo")
            fila = QHBoxLayout(caja)
            fila.setContentsMargins(14, 10, 14, 10)
            fila.setSpacing(14)
            nombre = QLabel(t["termino"], objectName="titulo_seccion", wordWrap=True)
            nombre.setFixedWidth(210)
            nombre.setStyleSheet(f"color: {tema.ACENTO};")
            fila.addWidget(nombre, 0, Qt.AlignTop)
            fila.addWidget(_texto(t["definicion"]), 1)
            fila.addWidget(QLabel(TIPOS.get(t.get("tipo"), ""), objectName="tenue"), 0, Qt.AlignTop)
            self.lista_glosario.addWidget(caja)
        if not visibles:
            self.lista_glosario.addWidget(QLabel("No hay ninguna palabra con eso.", objectName="tenue"))
        self.lista_glosario.addStretch()

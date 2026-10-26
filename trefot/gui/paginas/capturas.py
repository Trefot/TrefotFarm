"""Pagina Capturas: sacar y comprobar las imagenes de las cartas del equipo."""

import os
import time
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from trefot import cartas, juego, ventana
from trefot.equipo import recorte_para_plantilla
from trefot.gui import tema
from trefot.gui.comun import Pagina, a_pixmap
from trefot.modos import MODOS
from trefot.rutas import CAPTURAS
from trefot.vision import guardar_imagen, leer_imagen

LADO_TALENTO = 26  # mitad del lado del recorte alrededor del boton de talento


class TarjetaCarta(QFrame):
    """Una carta de la mano capturada, con su reconocimiento y un selector para guardarla."""

    def __init__(self, pagina, carta: cartas.Carta, equipo):
        super().__init__(objectName="tarjeta")
        self.carta, self.equipo, self.pagina = carta, equipo, pagina
        capa = QHBoxLayout(self)
        capa.setContentsMargins(8, 8, 8, 8)
        imagen = QLabel(alignment=Qt.AlignTop)
        imagen.setPixmap(a_pixmap(carta.imagen, 62))
        capa.addWidget(imagen)
        derecha = QVBoxLayout()
        derecha.setSpacing(4)
        color = tema.OK if carta.nombre else tema.AVISO
        nombre = equipo.defs[carta.nombre].descripcion if carta.nombre in equipo.defs else "¿no reconocida?"
        etiqueta = QLabel(f"<b>{carta.posicion + 1}.</b> <span style='color:{color}'>{nombre}</span>", wordWrap=True)
        derecha.addWidget(etiqueta)
        derecha.addWidget(QLabel(f"{carta.tipo.name.lower()} · {carta.rango.name.lower()}", objectName="tenue"))
        derecha.addStretch()
        self.combo = QComboBox()
        self.combo.view().setMinimumWidth(300)  # la lista desplegable, mas ancha que la tarjeta
        self.combo.addItem("Es...", None)
        for d in equipo.defs.values():
            if d.es_carta:
                self.combo.addItem(d.descripcion, d.nombre)
        derecha.addWidget(self.combo)
        boton = QPushButton("Guardar")
        boton.setStyleSheet("padding: 5px 4px;")
        boton.clicked.connect(self.guardar)
        derecha.addWidget(boton)
        capa.addLayout(derecha, 1)

    def guardar(self):
        nombre = self.combo.currentData()
        if not nombre:
            return
        guardar_imagen(self.equipo.ruta_propia(nombre), recorte_para_plantilla(self.carta.imagen))
        self.equipo.recargar()
        self.pagina.refrescar_lista()
        self.pagina.mensaje(f"Guardada '{nombre}'.")


class PaginaCapturas(Pagina):
    titulo = "Capturas"
    subtitulo = (
        "En una pelea pulsa 'Capturar mano' (o 'Desde foto...' para usar una foto guardada). En cada carta que falte, "
        "elige en 'Es...' cual es y pulsa Guardar. Repite hasta no tener ninguna ✖."
    )

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.equipo = None
        self.recorte_talento = None
        fila = QHBoxLayout()

        # ---- izquierda: estado de las capturas del equipo
        grupo = QGroupBox("Capturas del equipo")
        capa = QVBoxLayout(grupo)
        self.combo_modo = QComboBox()
        for modo in MODOS.values():
            if getattr(modo, "equipo", None) is not None:
                self.combo_modo.addItem(modo.nombre, modo.id)
        capa.addWidget(self.combo_modo)
        self.lista = QListWidget()
        capa.addWidget(self.lista)
        capa.addWidget(QLabel("✔ propia   ◐ imagen de AutoFarming   ✖ falta   ○ opcional", objectName="tenue", wordWrap=True))
        b_carpeta = QPushButton("Abrir carpeta de capturas")
        b_carpeta.clicked.connect(lambda: os.startfile(self.equipo.carpeta))
        capa.addWidget(b_carpeta)
        grupo.setMaximumWidth(380)
        fila.addWidget(grupo)

        # ---- derecha: herramientas
        der = QVBoxLayout()
        botones = QHBoxLayout()
        for texto, funcion, primario in (
            ("Capturar mano", self.capturar_mano, True),
            ("Desde foto...", self.mano_desde_foto, False),
            ("Probar", self.probar, False),
            ("Talento", self.capturar_talento, False),
            ("Foto completa", self.foto_completa, False),
            ("Ajustar", self.ajustar, False),
        ):
            b = QPushButton(texto, objectName="primario" if primario else "")
            b.clicked.connect(funcion)
            botones.addWidget(b)
        der.addLayout(botones)
        self.lbl_mensaje = QLabel(objectName="tenue", wordWrap=True)
        der.addWidget(self.lbl_mensaje)

        self.zona_mano = QWidget()
        self.capa_mano = QGridLayout(self.zona_mano)  # 2 filas de 4 cartas
        self.capa_mano.addWidget(QLabel("Aqui apareceran las 8 cartas de tu mano.", objectName="tenue", alignment=Qt.AlignCenter), 0, 0)
        desplazar = QScrollArea(widgetResizable=True)
        desplazar.setWidget(self.zona_mano)
        desplazar.setMinimumHeight(320)
        der.addWidget(desplazar)

        grupo_talento = QGroupBox("Talento de Odin")
        capa_talento = QHBoxLayout(grupo_talento)
        self.img_talento = QLabel("—", alignment=Qt.AlignCenter)
        self.img_talento.setFixedSize(70, 70)
        capa_talento.addWidget(self.img_talento)
        b_guardar_talento = QPushButton("Guardar como talento de Odin")
        b_guardar_talento.clicked.connect(self.guardar_talento)
        capa_talento.addWidget(b_guardar_talento)
        capa_talento.addWidget(QLabel("Cuando el boton del talento este disponible, pulsa 'Capturar talento'.", objectName="tenue", wordWrap=True), 1)
        der.addWidget(grupo_talento)
        der.addStretch()
        fila.addLayout(der, 1)
        self.cuerpo.addLayout(fila)

        self.combo_modo.currentIndexChanged.connect(self._cambiar_modo)
        self._cambiar_modo()

    def al_mostrar(self):
        self.equipo.recargar()
        self.refrescar_lista()

    def _cambiar_modo(self):
        self.equipo = MODOS[self.combo_modo.currentData()].equipo
        self.refrescar_lista()

    def refrescar_lista(self):
        self.lista.clear()
        for d, estado in self.equipo.estado():
            if estado == "propia":
                marca, color = "✔", tema.OK
            elif estado == "respaldo":
                marca, color = "◐", tema.AVISO
            elif d.obligatoria:
                marca, color = "✖", tema.ERROR
            else:
                marca, color = "○", tema.TENUE
            item = QListWidgetItem(f"{marca}  {d.descripcion}")
            item.setForeground(QColor(color))
            self.lista.addItem(item)
        self.app.refrescar_insignias()

    def mensaje(self, texto: str):
        self.lbl_mensaje.setText(texto)

    def _pantalla(self):
        try:
            return ventana.capturar()[0]
        except Exception as error:
            self.mensaje(str(error))
            return None

    def ajustar(self):
        ok = ventana.ajustar_tamano()
        self.mensaje("Ventana en 554x960." if ok else ventana.ultimo_error)

    def mano_desde_foto(self):
        """Etiquetar cartas desde una foto guardada (sin tener que estar en una pelea)."""
        ruta, _ = QFileDialog.getOpenFileName(self, "Elige una foto del juego en pelea", str(CAPTURAS), "Imagenes (*.png *.jpg)")
        if not ruta:
            return
        pantalla = leer_imagen(Path(ruta))
        if pantalla is None:
            self.mensaje("No pude abrir esa imagen.")
            return
        self.capturar_mano(pantalla, origen=Path(ruta).name)

    def capturar_mano(self, pantalla=None, origen: str = ""):
        if pantalla is None or isinstance(pantalla, bool):  # el boton pasa un bool
            pantalla = self._pantalla()
        if pantalla is None:
            return
        mano = self.equipo.etiquetar(cartas.leer_mano(pantalla))
        while self.capa_mano.count():
            widget = self.capa_mano.takeAt(0).widget()
            if widget:
                widget.setParent(None)  # que desaparezca ya, no al siguiente ciclo
                widget.deleteLater()
        for carta in mano:
            self.capa_mano.addWidget(TarjetaCarta(self, carta, self.equipo), carta.posicion // 4, carta.posicion % 4)
        reconocidas = sum(1 for c in mano if c.nombre)
        self.mensaje(f"Mano {'de ' + origen if origen else 'capturada'}: {reconocidas}/8 reconocidas. Huecos libres detectados: {cartas.contar_huecos(pantalla)}.")

    def capturar_talento(self):
        pantalla = self._pantalla()
        if pantalla is None:
            return
        x, y = juego.COORD["talento"]
        t = LADO_TALENTO
        self.recorte_talento = pantalla[max(0, y - t) : y + t, max(0, x - t) : x + t].copy()
        self.img_talento.setPixmap(a_pixmap(self.recorte_talento, 64))
        self.mensaje("Si en el recuadro se ve el boton del talento, pulsa 'Guardar como talento de Odin'.")

    def guardar_talento(self):
        if self.recorte_talento is None or "odin_talento" not in self.equipo.defs:
            return
        guardar_imagen(self.equipo.ruta_propia("odin_talento"), self.recorte_talento)
        self.equipo.recargar()
        self.refrescar_lista()
        self.mensaje("Talento de Odin guardado.")

    def probar(self):
        pantalla = self._pantalla()
        if pantalla is None:
            return
        self.equipo.recargar()
        mano = self.equipo.etiquetar(cartas.leer_mano(pantalla))
        talento = self.equipo.plantilla("odin_talento")
        visible = talento is not None and talento.esta(pantalla, 0.75)
        self.mensaje(
            "Reconocidas: " + "  ".join(str(c) for c in mano)
            + f"\nTalento de Odin visible: {'SI' if visible else 'NO'} · huecos libres: {cartas.contar_huecos(pantalla)}"
        )

    def foto_completa(self):
        pantalla = self._pantalla()
        if pantalla is None:
            return
        ruta = CAPTURAS / f"pantalla_{time.strftime('%Y%m%d_%H%M%S')}.png"
        guardar_imagen(ruta, pantalla)
        self.mensaje(f"Guardada en {ruta}")

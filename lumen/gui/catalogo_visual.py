"""Selector de aventuras: destino destacado y medallones navegables."""

from PyQt5.QtCore import Qt, QRectF, QVariantAnimation, QEasingCurve, QEvent, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QRadialGradient
from PyQt5.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from lumen.gui import iconos, tema
from lumen.modos import MODOS
from lumen.modos.catalogo import CATALOGO, BESTIAS, DEMONIOS, FUERTE, foto_de
from lumen.rutas import ASSETS


CATEGORIAS = (("Bestias", BESTIAS), ("Demonios", DEMONIOS), ("Solgres", FUERTE))


def _retrato(ruta, tamano, disponible):
    from lumen.gui.paginas.personajes import _en_gris

    pix = iconos.redondo(ruta, tamano, tema.ACENTO if disponible else tema.TENUE)
    return _en_gris(pix) if pix is not None and not disponible else pix


class MedallonContenido(QAbstractButton):
    """Una parada del selector, sin caja rectangular alrededor."""

    def __init__(self, contenido):
        super().__init__()
        self.contenido = contenido
        self.setCheckable(True)
        self.setFixedSize(132, 172)
        self.disponible = any(d.id in MODOS for d in contenido.destinos)
        self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName(contenido.nombre)
        self.setToolTip(
            contenido.nombre
            + " · "
            + contenido.descripcion
            + ("" if self.disponible else " · Próximamente")
        )
        self.setFocusPolicy(Qt.StrongFocus)
        self.imagen = _retrato(contenido.foto, 88, self.disponible)
        self.luz = 0.0
        self.animacion = QVariantAnimation(self)
        self.animacion.setDuration(170)
        self.animacion.setEasingCurve(QEasingCurve.OutCubic)
        self.animacion.valueChanged.connect(self._iluminar)

    def _iluminar(self, valor):
        self.luz = float(valor)
        self.update()

    def _animar(self, destino):
        self.animacion.stop()
        self.animacion.setStartValue(self.luz)
        self.animacion.setEndValue(destino)
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
        activo = self.isChecked()
        centro = self.rect().center().x()
        radio = 45 + self.luz * 3 + (3 if activo else 0)
        luz = QRadialGradient(centro, 55, 66)
        acento = tema.ACENTO if self.disponible else tema.TENUE
        color = QColor(acento)
        color.setAlpha(68 if activo else int(35 * self.luz))
        luz.setColorAt(0, color)
        luz.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), luz)
        p.setPen(
            QPen(
                QColor(acento if activo or self.hasFocus() else tema.BORDE),
                2 if activo else 1,
            )
        )
        p.setBrush(QColor(tema.PANEL))
        p.drawEllipse(
            QRectF(centro - radio - 4, 55 - radio - 4, (radio + 4) * 2, (radio + 4) * 2)
        )
        if self.imagen is not None:
            p.drawPixmap(
                QRectF(centro - radio, 55 - radio, radio * 2, radio * 2),
                self.imagen,
                QRectF(self.imagen.rect()),
            )
        else:
            p.drawText(
                QRectF(centro - radio, 55 - radio, radio * 2, radio * 2),
                Qt.AlignCenter,
                "7DS",
            )
        font = QFont("Segoe UI", 10)
        font.setBold(activo)
        p.setFont(font)
        p.setPen(
            QColor(acento if activo else tema.TEXTO if self.disponible else tema.TENUE)
        )
        p.drawText(
            QRectF(3, 113, self.width() - 6, 39),
            Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap,
            self.contenido.nombre,
        )
        if activo:
            p.setBrush(QColor(acento))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(centro - 3, 104, 6, 6))
        if not self.disponible:
            p.setFont(QFont("Segoe UI", 9))
            p.setPen(QColor(tema.TENUE))
            p.drawText(
                QRectF(2, 151, self.width() - 4, 19), Qt.AlignCenter, "Próximamente"
            )
        p.end()


class EscenaDestino(QFrame):
    """Ilustracion circular sobre un fondo abierto, sin marco de tarjeta."""

    def __init__(self):
        super().__init__()
        self.setObjectName("escena_destino")
        self.setMinimumHeight(300)
        self.imagen = None
        self.disponible = True
        self.fondo = QPixmap(str(ASSETS / "interfaz" / "taberna.png"))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def poner(self, destino_id):
        self.disponible = destino_id in MODOS
        self.imagen = _retrato(foto_de(destino_id), 202, self.disponible)
        self.update()

    def paintEvent(self, evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        # La luz se funde con la pagina; no hay un rectangulo que encierre el destino.
        centro_x, centro_y = self.width() - 155, self.height() / 2 - 5
        if tema.SKIN.id == "taberna_viva" and not self.fondo.isNull():
            p.setOpacity(0.10)
            p.drawPixmap(self.rect(), self.fondo)
            p.setOpacity(1)
        luz = QRadialGradient(centro_x, centro_y, 230)
        color = QColor(tema.ACENTO if self.disponible else tema.TENUE)
        color.setAlpha(52)
        luz.setColorAt(0, color)
        color = QColor(tema.FONDO)
        color.setAlpha(0)
        luz.setColorAt(1, color)
        p.fillRect(self.rect(), luz)
        # Orbitas abiertas en vez de un recuadro repetido.
        p.setPen(QPen(QColor(tema.BORDE), 1))
        p.drawArc(QRectF(centro_x - 135, centro_y - 135, 270, 270), 22 * 16, 282 * 16)
        p.drawArc(QRectF(centro_x - 148, centro_y - 148, 296, 296), 200 * 16, 104 * 16)
        p.setPen(QPen(QColor(tema.ACENTO if self.disponible else tema.TENUE), 2))
        p.drawArc(QRectF(centro_x - 122, centro_y - 122, 244, 244), 38 * 16, 62 * 16)
        if self.imagen is not None:
            p.drawPixmap(
                QRectF(centro_x - 101, centro_y - 101, 202, 202),
                self.imagen,
                QRectF(self.imagen.rect()),
            )
        p.end()


class CatalogoVisual(QWidget):
    elegido = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("contenido_desplazable")
        self.seleccion = None
        self.visibles = []
        self.destino_id = None
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(10)
        self.grupo = QTabBar(objectName="categorias_contenido")
        self.grupo.setExpanding(True)
        self.grupo.setDrawBase(False)
        self.grupo.setAccessibleName("Categoría de contenidos")
        for nombre, grupo in CATEGORIAS:
            indice = self.grupo.addTab(nombre)
            self.grupo.setTabData(indice, grupo)
        capa.addWidget(self.grupo)
        self.buscar = QLineEdit(placeholderText="Buscar en Bestias…")
        self.buscar.setClearButtonEnabled(True)
        self.buscar.setMinimumHeight(36)
        capa.addWidget(self.buscar)
        self.escena = EscenaDestino()
        zona = QHBoxLayout(self.escena)
        zona.setContentsMargins(20, 18, 12, 18)
        detalles = QVBoxLayout()
        detalles.setSpacing(10)
        self.categoria = QLabel(objectName="rotulo_aventura")
        self.nombre = QLabel(objectName="titulo_hero", wordWrap=True)
        self.descripcion = QLabel(objectName="detalle_aventura", wordWrap=True)
        self.estado = QLabel(objectName="tenue", wordWrap=True)
        self.pisos = QComboBox()
        self.pisos.setAccessibleName("Piso o dificultad del destino")
        self.pisos.currentIndexChanged.connect(self._cambiar_piso)
        self.preparar = QPushButton("Preparar esta aventura  →", objectName="primario")
        self.preparar.clicked.connect(self._abrir)
        for w in (self.categoria, self.nombre, self.descripcion, self.estado):
            detalles.addWidget(w)
        self.pisos.setMinimumWidth(190)
        self.pisos.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.pisos.setMinimumContentsLength(18)
        self.piso_unico = QLabel(objectName="detalle_aventura", wordWrap=True)
        detalles.addWidget(self.piso_unico)
        self.fila_pisos = QHBoxLayout()
        self.fila_pisos.addWidget(self.pisos)
        self.fila_pisos.addStretch()
        detalles.addLayout(self.fila_pisos)
        acciones = QHBoxLayout()
        acciones.addWidget(self.preparar)
        acciones.addStretch()
        detalles.addLayout(acciones)
        detalles.addStretch()
        zona.addLayout(detalles, 1)
        self.reserva_imagen = QWidget(objectName="reserva_ilustracion")
        self.reserva_imagen.setStyleSheet("background: transparent;")
        self.reserva_imagen.setFixedWidth(300)
        self.reserva_imagen.setAttribute(Qt.WA_TransparentForMouseEvents)
        zona.addWidget(self.reserva_imagen)
        capa.addWidget(self.escena)
        self.vacio = QLabel(
            "No encontramos ese destino. Prueba otro nombre o cambia el grupo.",
            wordWrap=True,
        )
        capa.addWidget(self.vacio)
        cabecera = QHBoxLayout()
        self.rotulo_destinos = QLabel("Elige una bestia", objectName="titulo_card")
        cabecera.addWidget(self.rotulo_destinos)
        self.contador = QLabel(objectName="tenue")
        cabecera.addWidget(self.contador)
        cabecera.addStretch()
        self.anterior = QPushButton("←", objectName="flecha_destino")
        self.siguiente = QPushButton("→", objectName="flecha_destino")
        self.anterior.setAccessibleName("Destino anterior")
        self.siguiente.setAccessibleName("Destino siguiente")
        self.anterior.clicked.connect(lambda: self._avanzar(-1))
        self.siguiente.clicked.connect(lambda: self._avanzar(1))
        cabecera.addWidget(self.anterior)
        cabecera.addWidget(self.siguiente)
        capa.addLayout(cabecera)
        self.tira = QScrollArea(widgetResizable=True, frameShape=QFrame.NoFrame)
        self.tira.setObjectName("tira_destinos")
        self.tira.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tira.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tira.setFixedHeight(194)
        self.tira.viewport().installEventFilter(self)
        soporte = QWidget(objectName="contenido_desplazable")
        fila = QHBoxLayout(soporte)
        fila.setContentsMargins(4, 4, 4, 4)
        fila.setSpacing(8)
        self.tarjetas = []
        for contenido in CATALOGO:
            boton = MedallonContenido(contenido)
            boton.clicked.connect(lambda _, c=contenido: self.seleccionar(c))
            fila.addWidget(boton)
            self.tarjetas.append((contenido, boton))
        fila.addStretch()
        self.tira.setWidget(soporte)
        capa.addWidget(self.tira)
        self.buscar.textChanged.connect(self.pintar)
        self.grupo.currentChanged.connect(self._cambiar_grupo)
        self.pintar()

    def _cambiar_piso(self):
        self.destino_id = self.pisos.currentData()
        self.escena.poner(self.destino_id)
        listo = self.destino_id in MODOS
        self.estado.setText(
            "Disponible para preparar"
            if listo
            else "Próximamente · puedes consultar sus detalles"
        )
        self.preparar.setText(
            "Preparar esta aventura  →" if listo else "Ver detalles  →"
        )
        self.preparar.setObjectName("primario" if listo else "consultar_destino")
        self.preparar.style().unpolish(self.preparar)
        self.preparar.style().polish(self.preparar)
        self.nombre.setStyleSheet("" if listo else f"color: {tema.TENUE};")

    def _abrir(self):
        if self.destino_id:
            self.elegido.emit(self.destino_id)

    def seleccionar(self, contenido):
        self.seleccion = contenido
        self.categoria.setText(contenido.grupo.upper())
        self.nombre.setText(contenido.nombre)
        self.descripcion.setText(contenido.descripcion)
        self.pisos.blockSignals(True)
        self.pisos.clear()
        for d in contenido.destinos:
            self.pisos.addItem(
                (d.nombre.replace("Floor", "Piso") or "Contenido completo")
                + (" · Próximamente" if d.id not in MODOS else ""),
                d.id,
            )
        disponibles = [i for i, d in enumerate(contenido.destinos) if d.id in MODOS]
        self.pisos.setCurrentIndex(disponibles[-1] if disponibles else 0)
        self.pisos.blockSignals(False)
        self.pisos.setVisible(self.pisos.count() > 1)
        self.piso_unico.setVisible(self.pisos.count() == 1)
        self.piso_unico.setText(self.pisos.currentText())
        self._cambiar_piso()
        for c, boton in self.tarjetas:
            boton.setChecked(c.id == contenido.id)
            boton.update()
            if c.id == contenido.id:
                self.tira.ensureWidgetVisible(boton, 20, 0)

    def _avanzar(self, paso):
        if self.visibles:
            i = (
                self.visibles.index(self.seleccion)
                if self.seleccion in self.visibles
                else 0
            )
            self.seleccionar(self.visibles[(i + paso) % len(self.visibles)])

    def pintar(self):
        consulta = self.buscar.text().strip().casefold()
        grupo = self.grupo.tabData(self.grupo.currentIndex())
        self.visibles = []
        for contenido, boton in self.tarjetas:
            coincide = (not grupo or contenido.grupo == grupo) and consulta in (
                contenido.nombre + " " + contenido.descripcion + " " + contenido.grupo
            ).casefold()
            boton.setVisible(coincide)
            if coincide:
                self.visibles.append(contenido)
        self.contador.setText(
            f"{len(self.visibles)} "
            + ("destino" if len(self.visibles) == 1 else "destinos")
        )
        self._ajustar_medallones()
        self.vacio.setVisible(not self.visibles)
        self.escena.setVisible(bool(self.visibles))
        self.tira.setVisible(bool(self.visibles))
        self.anterior.setEnabled(len(self.visibles) > 1)
        self.siguiente.setEnabled(len(self.visibles) > 1)
        if self.visibles:
            self.seleccionar(
                self.seleccion if self.seleccion in self.visibles else self.visibles[0]
            )
        else:
            self.seleccion = None
            self.destino_id = None

    def _cambiar_grupo(self):
        indice = self.grupo.currentIndex()
        self.buscar.blockSignals(True)
        self.buscar.clear()
        self.buscar.blockSignals(False)
        self.buscar.setPlaceholderText(f"Buscar en {CATEGORIAS[indice][0]}…")
        self.rotulo_destinos.setText(
            ("Elige una bestia", "Elige un demonio", "Contenidos de Solgres")[indice]
        )
        self.pintar()

    def _ajustar_medallones(self):
        if not hasattr(self, "tarjetas") or not self.visibles:
            return
        cantidad = len(self.visibles)
        ancho = max(
            112, min(142, (self.tira.viewport().width() - 8 - cantidad * 8) // cantidad)
        )
        for contenido, boton in self.tarjetas:
            if contenido in self.visibles:
                boton.setFixedSize(ancho, 172)

    def eventFilter(self, objeto, evento):
        if objeto is self.tira.viewport() and evento.type() == QEvent.Resize:
            self._ajustar_medallones()
        return super().eventFilter(objeto, evento)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self.reserva_imagen.setFixedWidth(240)
        self._ajustar_medallones()

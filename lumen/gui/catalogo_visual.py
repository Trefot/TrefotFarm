"""Selector de aventuras: destino destacado y medallones navegables."""

from PyQt5.QtCore import Qt, QRectF, QVariantAnimation, QEasingCurve, pyqtSignal
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
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from lumen.gui import iconos, tema
from lumen.modos import MODOS
from lumen.modos.catalogo import CATALOGO, GRUPOS, foto_de
from lumen.rutas import ASSETS


class MedallonContenido(QAbstractButton):
    """Una parada del selector, sin caja rectangular alrededor."""

    def __init__(self, contenido):
        super().__init__()
        self.contenido = contenido
        self.setCheckable(True)
        self.setFixedSize(142, 156)
        self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName(contenido.nombre)
        self.setToolTip(contenido.nombre + " · " + contenido.descripcion)
        self.setFocusPolicy(Qt.StrongFocus)
        self.imagen = iconos.redondo(contenido.foto, 88, tema.BORDE)
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
        color = QColor(tema.ACENTO)
        color.setAlpha(68 if activo else int(35 * self.luz))
        luz.setColorAt(0, color)
        luz.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), luz)
        p.setPen(
            QPen(
                QColor(tema.ACENTO if activo or self.hasFocus() else tema.BORDE),
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
        p.setPen(QColor(tema.ACENTO if activo else tema.TEXTO))
        p.drawText(
            QRectF(3, 113, self.width() - 6, 39),
            Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap,
            self.contenido.nombre,
        )
        if activo:
            p.setBrush(QColor(tema.ACENTO))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(centro - 3, 104, 6, 6))
        p.end()


class EscenaDestino(QFrame):
    """Ilustracion circular sobre un fondo abierto, sin marco de tarjeta."""

    def __init__(self):
        super().__init__()
        self.setObjectName("escena_destino")
        self.setMinimumHeight(330)
        self.imagen = None
        self.fondo = QPixmap(str(ASSETS / "interfaz" / "taberna.png"))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def poner(self, destino_id):
        self.imagen = iconos.redondo(foto_de(destino_id), 202, tema.ACENTO)
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
        color = QColor(tema.ACENTO)
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
        p.setPen(QPen(QColor(tema.ACENTO), 2))
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
        capa.setSpacing(14)
        filtros = QHBoxLayout()
        self.buscar = QLineEdit(
            placeholderText="¿A dónde vamos? Busca una bestia, un demonio…"
        )
        self.buscar.setClearButtonEnabled(True)
        self.grupo = QComboBox()
        self.grupo.addItem("Todos los contenidos", "")
        for grupo in GRUPOS:
            self.grupo.addItem(grupo, grupo)
        filtros.addWidget(self.buscar, 1)
        filtros.addWidget(self.grupo)
        capa.addLayout(filtros)
        self.escena = EscenaDestino()
        zona = QHBoxLayout(self.escena)
        zona.setContentsMargins(24, 24, 12, 24)
        detalles = QVBoxLayout()
        detalles.setSpacing(14)
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
        acciones = QHBoxLayout()
        acciones.addWidget(self.pisos)
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
        cabecera.addWidget(QLabel("Elige tu destino", objectName="titulo_card"))
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
        self.tira.setFixedHeight(182)
        soporte = QWidget(objectName="contenido_desplazable")
        fila = QHBoxLayout(soporte)
        fila.setContentsMargins(4, 4, 4, 4)
        fila.setSpacing(10)
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
        self.grupo.currentIndexChanged.connect(self.pintar)
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
                (d.nombre or "Contenido completo")
                + (" · Próximamente" if d.id not in MODOS else ""),
                d.id,
            )
        disponibles = [i for i, d in enumerate(contenido.destinos) if d.id in MODOS]
        self.pisos.setCurrentIndex(disponibles[-1] if disponibles else 0)
        self.pisos.blockSignals(False)
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
        grupo = self.grupo.currentData()
        self.visibles = []
        for contenido, boton in self.tarjetas:
            coincide = (not grupo or contenido.grupo == grupo) and consulta in (
                contenido.nombre + " " + contenido.descripcion + " " + contenido.grupo
            ).casefold()
            boton.setVisible(coincide)
            if coincide:
                self.visibles.append(contenido)
        self.contador.setText(f"{len(self.visibles)} destinos")
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

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self.reserva_imagen.setFixedWidth(270 if self.width() < 1000 else 300)

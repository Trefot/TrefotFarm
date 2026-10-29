"""Metas de material en Farmear (pestana "Metas", junto a Registro, Plan y Opciones): cada meta con su
avance, lo que tienes y quieres (se cambia en la misma fila), donde farmearla y un boton para hacerlo.
Se anaden tocando un objeto de "Puedes conseguir" (Inicio o Farmear)."""

from PyQt5.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget

from lumen import metas, premios
from lumen.gui import iconos, tema
from lumen.modos import MODOS
from lumen.modos.catalogo import foto_de

ICONO = "mdi6.bullseye-arrow"
GUARDAR_MS = 800  # tras teclear un numero, guardar cuando se deja de escribir


def barra(actual: int, quiero: int, alto: int = 6, ancho: int | None = None) -> QProgressBar:
    """Barra de avance: dorada mientras falta, verde al completarla."""
    b = QProgressBar(maximum=max(1, quiero), value=min(actual, quiero), textVisible=False)
    b.setFixedHeight(alto)
    if ancho:
        b.setFixedWidth(ancho)
    color = tema.OK if actual >= quiero else tema.ACENTO
    b.setStyleSheet(f"QProgressBar {{ background: {tema.SKIN.hundido}; border: none; border-radius: {alto // 2}px; }}"
                    f"QProgressBar::chunk {{ background: {color}; border-radius: {alto // 2}px; }}")
    return b


def marcar_meta(casilla: QFrame, prob: QLabel, objeto: str, todas: list[metas.Meta], ancho: int):
    """Una casilla de "Puedes conseguir": si el objeto es meta, borde dorado, barrita y "12/40" en lugar
    del %; si no, el aviso de que tocandolo se hace meta."""
    meta = metas.de(objeto, todas)
    if meta is None:
        casilla.setToolTip(casilla.toolTip() + "<br>Toca para hacerlo meta.")
        return
    color = tema.OK if meta.completa else tema.ACENTO
    casilla.setStyleSheet(f"QFrame#{casilla.objectName()} {{ border: 2px solid {color}; }}")
    prob.setText(f"{meta.actual}/{meta.quiero}")
    prob.setStyleSheet(f"color: {color}; font-weight: 700;")
    casilla.layout().insertWidget(1, barra(meta.actual, meta.quiero, 4, ancho), 0, Qt.AlignHCenter)
    casilla.setToolTip(f"<b>Meta: {meta.actual} de {meta.quiero}</b> · toca para cambiarla<br>" + casilla.toolTip())


def icono(objeto: str, tam: int) -> QPixmap:
    pix = QPixmap(str(premios.ICONOS / f"{objeto}.png"))
    if pix.isNull():
        return iconos.pixmap("mdi6.help-box", tam, tema.TENUE)
    return pix.scaled(tam, tam, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def estimacion(meta: metas.Meta) -> str:
    """'Mejor: Skollandhati & Hati · Floor 4 · faltan ≈13 victorias · ≈35 min'."""
    if meta.completa:
        return f"<span style='color:{tema.OK}'>✓ Completada</span>"
    mejor = metas.mejor_destino(meta.objeto)
    if not mejor:
        return "El bot todavía no farmea ningún sitio donde salga."
    destino, por_victoria = mejor
    victorias = metas.victorias_para(meta.faltan, por_victoria)
    texto = f"Mejor: <b>{MODOS[destino].nombre}</b> · faltan ≈{victorias} victoria{'s' if victorias != 1 else ''}"
    from lumen.gui.paginas.equipos import mas_rapido

    rapido = mas_rapido(destino)
    if rapido:
        minutos = victorias * rapido["minutos"]
        texto += f" · ≈{minutos / 60:.1f} h".replace(".", ",") if minutos >= 90 else f" · ≈{max(1, round(minutos))} min"
    return texto


class FilaMeta(QFrame):
    """Una meta: icono, nombre, barra, tengo/quiero editables, donde farmearla, Farmear y quitar."""

    def __init__(self, panel: "PanelMetas", meta: metas.Meta):
        super().__init__(objectName="tarea_plan")
        self.panel, self.objeto = panel, meta.objeto
        fuera = QVBoxLayout(self)
        fuera.setContentsMargins(8, 6, 6, 6)
        fuera.setSpacing(4)
        capa = QHBoxLayout()
        capa.setSpacing(10)
        dibujo = QLabel()
        dibujo.setPixmap(icono(meta.objeto, 42))
        capa.addWidget(dibujo, 0, Qt.AlignTop)
        centro = QVBoxLayout()
        centro.setSpacing(3)
        arriba = QHBoxLayout()
        arriba.addWidget(QLabel(f"<b>{meta.nombre}</b>", wordWrap=True), 1)
        self.cuenta = QLabel()
        arriba.addWidget(self.cuenta, 0, Qt.AlignTop)
        centro.addLayout(arriba)
        self.caja_barra = QVBoxLayout()
        centro.addLayout(self.caja_barra)
        self.donde = QLabel(objectName="tenue", wordWrap=True)
        centro.addWidget(self.donde)
        capa.addLayout(centro, 1)
        fuera.addLayout(capa)

        abajo = QHBoxLayout()  # en otra linea: la columna de Farmear es estrecha
        abajo.setSpacing(6)
        abajo.addSpacing(52)
        self.tengo = QSpinBox(maximum=999_999, prefix="Tengo ")
        self.quiero = QSpinBox(minimum=1, maximum=999_999, prefix="Quiero ")
        for spin in (self.tengo, self.quiero):
            spin.valueChanged.connect(self._cambiado)
            abajo.addWidget(spin, 1)
        self.b_farmear = QPushButton(objectName="chico")
        self.b_farmear.setIcon(iconos.icono("jugar", tema.ACENTO))
        self.b_farmear.setIconSize(QSize(16, 16))
        self.b_farmear.setToolTip("Farmear donde mejor sale, hasta completar la meta")
        self.b_farmear.clicked.connect(self._farmear)
        abajo.addWidget(self.b_farmear)
        quitar = QPushButton(objectName="chico")
        quitar.setFlat(True)
        quitar.setIcon(iconos.icono("mdi6.close", tema.TENUE))
        quitar.setToolTip("Quitar la meta")
        quitar.clicked.connect(lambda: panel.quitar(self.objeto))
        abajo.addWidget(quitar)
        fuera.addLayout(abajo)
        self._guardar = QTimer(self, singleShot=True, interval=GUARDAR_MS, timeout=self._guardar_cifras)
        self.actualizar(meta)

    def actualizar(self, meta: metas.Meta):
        for spin, valor in ((self.tengo, meta.actual), (self.quiero, meta.quiero)):
            if not spin.hasFocus():
                spin.blockSignals(True)
                spin.setValue(valor)
                spin.blockSignals(False)
        self.cuenta.setText(f"{meta.actual} / {meta.quiero}")
        self.cuenta.setStyleSheet(f"color: {tema.OK if meta.completa else tema.TEXTO}; font-weight: 700;")
        while self.caja_barra.count():
            w = self.caja_barra.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.caja_barra.addWidget(barra(meta.actual, meta.quiero))
        self.donde.setText(estimacion(meta))
        self.b_farmear.setVisible(not meta.completa and metas.mejor_destino(meta.objeto) is not None)

    def _cambiado(self):
        self._guardar.start()

    def _guardar_cifras(self):
        metas.poner(self.objeto, self.tengo.value(), self.quiero.value())
        self.panel.cambiado.emit()
        meta = metas.de(self.objeto, metas.cargar(fresco=True))
        if meta:
            self.actualizar(meta)

    def _farmear(self):
        mejor = metas.mejor_destino(self.objeto)
        if mejor:
            self.panel.farmear.emit(mejor[0])


class PanelMetas(QFrame):
    farmear = pyqtSignal(str)  # id del destino donde farmear la meta
    cambiado = pyqtSignal()  # se creo, cambio o quito una meta

    def __init__(self):
        super().__init__(objectName="seccion")
        capa = QVBoxLayout(self)
        capa.setSpacing(6)
        capa.addWidget(QLabel("Toca un objeto de «Puedes conseguir» para hacerlo meta. Cada victoria del bot "
                              "suma el botín que reconoce.", objectName="tenue", wordWrap=True))
        zona = QWidget()
        self.lista = QVBoxLayout(zona)
        self.lista.setContentsMargins(0, 0, 4, 0)
        self.lista.setSpacing(4)
        self.desliza = QScrollArea(objectName="area_pagina", widgetResizable=True, frameShape=QFrame.NoFrame)
        self.desliza.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.desliza.setWidget(zona)
        capa.addWidget(self.desliza, 1)
        self.filas: dict[str, FilaMeta] = {}
        self.pintar()

    def pintar(self):
        while self.lista.count():
            w = self.lista.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.filas = {}
        todas = metas.cargar(fresco=True)
        for meta in sorted(todas, key=lambda m: m.completa):  # las completadas, al final
            self.filas[meta.objeto] = FilaMeta(self, meta)
            self.lista.addWidget(self.filas[meta.objeto])
        if not todas:
            self.lista.addWidget(QLabel("Aún no tienes metas.", objectName="tenue"))
        self.lista.addStretch()

    def refrescar(self):
        """Avance de cada meta (sin rehacer las filas, para no perder lo que se esta escribiendo)."""
        todas = {m.objeto: m for m in metas.cargar()}
        if set(todas) != set(self.filas):
            self.pintar()
            return
        for objeto, fila in self.filas.items():
            fila.actualizar(todas[objeto])

    def anadir(self, objeto: str):
        """Hace meta un objeto (si no lo era) y lo deja listo para escribir cuanto quieres."""
        if metas.de(objeto, metas.cargar(fresco=True)) is None:
            mejor = metas.mejor_destino(objeto)
            sugerido = max(10, round(mejor[1] * 10)) if mejor else 10  # unas 10 victorias
            metas.poner(objeto, 0, sugerido)
            self.cambiado.emit()
        self.pintar()
        fila = self.filas.get(objeto)
        if fila:
            QTimer.singleShot(0, lambda: (self.desliza.ensureWidgetVisible(fila), fila.quiero.setFocus(),
                                          fila.quiero.selectAll()))

    def quitar(self, objeto: str):
        metas.quitar(objeto)
        self.cambiado.emit()
        self.pintar()

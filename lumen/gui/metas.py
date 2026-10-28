"""Metas de material en la interfaz: el dialogo de una meta (al tocar un objeto) y el panel con todas."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from lumen import metas, premios
from lumen.gui import iconos, tema
from lumen.modos import MODOS
from lumen.modos.catalogo import foto_de

ICONO = "mdi6.bullseye-arrow"


def barra(actual: int, quiero: int, alto: int = 6) -> QProgressBar:
    """Barra de avance: dorada mientras falta, verde al completarla."""
    b = QProgressBar(maximum=max(1, quiero), value=min(actual, quiero), textVisible=False)
    b.setFixedHeight(alto)
    color = tema.OK if actual >= quiero else tema.ACENTO
    b.setStyleSheet(f"QProgressBar {{ background: {tema.SKIN.hundido}; border: none; border-radius: {alto // 2}px; }}"
                    f"QProgressBar::chunk {{ background: {color}; border-radius: {alto // 2}px; }}")
    return b


def icono(objeto: str, tam: int) -> QPixmap:
    pix = QPixmap(str(premios.icono_de(objeto)))
    if pix.isNull():
        return iconos.pixmap("mdi6.help-box", tam, tema.TENUE)
    return pix.scaled(tam, tam, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def texto_tiempo(minutos: float) -> str:
    return f"≈{minutos / 60:.1f} h".replace(".", ",") if minutos >= 90 else f"≈{max(1, round(minutos))} min"


def estimacion(meta: metas.Meta) -> str:
    """'faltan ≈13 victorias · ≈35 min' en el mejor sitio para farmearla ('' si no hay ninguno listo)."""
    mejor = metas.mejor_destino(meta.objeto)
    if not mejor or meta.completa:
        return ""
    destino, por_victoria = mejor
    victorias = metas.victorias_para(meta.faltan, por_victoria)
    texto = f"≈{victorias} victoria{'s' if victorias != 1 else ''}"
    from lumen.gui.paginas.equipos import mas_rapido

    rapido = mas_rapido(destino)
    if rapido:
        texto += f" · {texto_tiempo(victorias * rapido['minutos'])}"
    return texto


class DialogoMeta(QDialog):
    """Crear, cambiar o quitar la meta de un objeto, con donde sale y cuanto falta."""

    def __init__(self, padre, objeto: str):
        super().__init__(padre)
        self.objeto = objeto
        info = premios.info(objeto)
        self.meta = metas.de(objeto)
        self.setWindowTitle("Meta" if self.meta else "Nueva meta")
        self.setMinimumWidth(500)
        capa = QVBoxLayout(self)
        capa.setContentsMargins(20, 18, 20, 16)
        capa.setSpacing(10)

        arriba = QHBoxLayout()
        dibujo = QLabel()
        dibujo.setPixmap(icono(objeto, 72))
        arriba.addWidget(dibujo)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        textos.addWidget(QLabel(info.get("nombre", objeto), objectName="titulo_seccion"))
        textos.addWidget(QLabel(info.get("descripcion", ""), objectName="tenue", wordWrap=True))
        arriba.addLayout(textos, 1)
        capa.addLayout(arriba)

        cifras = QGridLayout()
        cifras.setHorizontalSpacing(12)
        cifras.addWidget(QLabel("Ya tengo"), 0, 0)
        self.tengo = QSpinBox(maximum=999_999, value=self.meta.actual if self.meta else 0)
        cifras.addWidget(self.tengo, 0, 1)
        cifras.addWidget(QLabel("Quiero"), 0, 2)
        self.quiero = QSpinBox(minimum=1, maximum=999_999, value=self.meta.quiero if self.meta else 10)
        cifras.addWidget(self.quiero, 0, 3)
        cifras.setColumnStretch(4, 1)
        capa.addLayout(cifras)

        capa.addWidget(QLabel("Dónde sale", objectName="titulo_seccion"))
        mejor = metas.mejor_destino(objeto)
        for destino, por_victoria in premios.donde_sale(objeto)[:4]:
            listo = destino in MODOS
            fila = QFrame(objectName="seccion")
            f = QHBoxLayout(fila)
            f.setContentsMargins(10, 6, 10, 6)
            foto = QLabel()
            pix = iconos.redondo(foto_de(destino), 34, tema.ACENTO if listo else tema.BORDE)
            if pix:
                foto.setPixmap(pix)
            f.addWidget(foto)
            nombre = MODOS[destino].nombre if listo else destino.replace("_", " ").capitalize()
            media = f"{por_victoria:.1f}".replace(".", ",").replace(",0", "")
            f.addWidget(QLabel(f"<b>{nombre}</b><br><span style='color:{tema.TENUE}'>≈{media} por victoria"
                               + ("" if listo else " · el bot aún no lo farmea") + "</span>"), 1)
            if mejor and destino == mejor[0]:
                m = QLabel("⚡ Mejor")
                m.setStyleSheet(f"color: {tema.ACENTO}; font-weight: 700;")
                f.addWidget(m)
            capa.addWidget(fila)
        self.resumen = QLabel(wordWrap=True)
        capa.addWidget(self.resumen)
        if not info.get("galeria"):
            capa.addWidget(QLabel("Este objeto el bot aún no lo cuenta solo: cambia «Ya tengo» a mano.",
                                  objectName="tenue", wordWrap=True))
        capa.addStretch()

        botones = QHBoxLayout()
        if self.meta:
            b_quitar = QPushButton(" Quitar meta")
            b_quitar.setIcon(iconos.icono("mdi6.close", tema.TEXTO))
            b_quitar.clicked.connect(self._quitar)
            botones.addWidget(b_quitar)
        botones.addStretch()
        b_cancelar = QPushButton("Cancelar")
        b_cancelar.clicked.connect(self.reject)
        botones.addWidget(b_cancelar)
        b_guardar = QPushButton(" Guardar meta", objectName="primario")
        b_guardar.setIcon(iconos.icono(ICONO, tema.SOBRE_ACENTO))
        b_guardar.clicked.connect(self._guardar)
        botones.addWidget(b_guardar)
        capa.addLayout(botones)
        self.tengo.valueChanged.connect(self._pintar_resumen)
        self.quiero.valueChanged.connect(self._pintar_resumen)
        self._pintar_resumen()

    def _pintar_resumen(self):
        meta = metas.Meta(self.objeto, self.tengo.value(), self.quiero.value(), 0)
        if meta.completa:
            self.resumen.setText(f"<span style='color:{tema.OK}'>✓ Ya la tienes completa.</span>")
            return
        donde = metas.mejor_destino(self.objeto)
        texto = f"Te faltan <b>{meta.faltan}</b>"
        if donde:
            texto += f": unas <b>{estimacion(meta)}</b> en {MODOS[donde[0]].nombre}."
        else:
            texto += ". El bot todavía no farmea ningún sitio donde salga."
        self.resumen.setText(texto)

    def _guardar(self):
        metas.poner(self.objeto, self.tengo.value(), self.quiero.value())
        self.accept()

    def _quitar(self):
        metas.quitar(self.objeto)
        self.accept()


class PanelMetas(QDialog):
    """Todas las metas: avance, donde farmear cada una y un boton para dejarlo listo en Inicio."""

    farmear = pyqtSignal(str)  # id del destino

    def __init__(self, padre):
        super().__init__(padre)
        self.setWindowTitle("Metas de material")
        self.resize(660, 480)
        capa = QVBoxLayout(self)
        capa.setContentsMargins(18, 16, 18, 16)
        capa.setSpacing(10)
        cab = QHBoxLayout()
        dibujo = QLabel()
        dibujo.setPixmap(iconos.pixmap(ICONO, 22, tema.ACENTO))
        cab.addWidget(dibujo)
        cab.addWidget(QLabel("Metas de material", objectName="titulo_seccion"))
        cab.addStretch()
        capa.addLayout(cab)
        zona = QWidget()
        self.lista = QVBoxLayout(zona)
        self.lista.setContentsMargins(0, 0, 4, 0)
        desliza = QScrollArea(widgetResizable=True, frameShape=QFrame.NoFrame)
        desliza.setWidget(zona)
        capa.addWidget(desliza, 1)
        capa.addWidget(QLabel("Para una meta nueva, toca un objeto de «Puedes conseguir» en Inicio. "
                              "Cada victoria del bot suma el botín que reconoce.", objectName="tenue", wordWrap=True))
        self.pintar()

    def pintar(self):
        while self.lista.count():
            w = self.lista.takeAt(0).widget()
            if w:
                w.deleteLater()
        todas = metas.cargar()
        for meta in sorted(todas, key=lambda m: m.completa):
            self.lista.addWidget(self._fila(meta))
        if not todas:
            self.lista.addWidget(QLabel("Aún no tienes metas.", objectName="tenue"))
        self.lista.addStretch()

    def _fila(self, meta: metas.Meta) -> QFrame:
        fila = QFrame(objectName="seccion")
        f = QHBoxLayout(fila)
        f.setContentsMargins(10, 8, 10, 8)
        f.setSpacing(12)
        dibujo = QLabel()
        dibujo.setPixmap(icono(meta.objeto, 48))
        f.addWidget(dibujo)
        centro = QVBoxLayout()
        centro.setSpacing(3)
        arriba = QHBoxLayout()
        arriba.addWidget(QLabel(f"<b>{meta.nombre}</b>"))
        arriba.addStretch()
        cuenta = QLabel(f"{meta.actual} / {meta.quiero}")
        cuenta.setStyleSheet(f"color: {tema.OK if meta.completa else tema.TEXTO}; font-weight: 700;")
        arriba.addWidget(cuenta)
        centro.addLayout(arriba)
        centro.addWidget(barra(meta.actual, meta.quiero))
        mejor = metas.mejor_destino(meta.objeto)
        if meta.completa:
            centro.addWidget(QLabel(f"<span style='color:{tema.OK}'>✓ Completada</span>"))
        elif mejor:
            centro.addWidget(QLabel(f"Mejor: <b>{MODOS[mejor[0]].nombre}</b> · faltan {estimacion(meta)}", objectName="tenue"))
        else:
            centro.addWidget(QLabel("El bot todavía no farmea ningún sitio donde salga.", objectName="tenue"))
        f.addLayout(centro, 1)
        if mejor and not meta.completa:
            foto = QLabel()
            pix = iconos.redondo(foto_de(mejor[0]), 34, tema.ACENTO)
            if pix:
                foto.setPixmap(pix)
            f.addWidget(foto)
            b = QPushButton(" Farmear", objectName="primario")
            b.setIcon(iconos.icono("jugar", tema.SOBRE_ACENTO))
            b.setToolTip("Lo deja listo en Inicio para parar al completar la meta")
            b.clicked.connect(lambda _=False, d=mejor[0]: (self.farmear.emit(d), self.accept()))
            f.addWidget(b)
        editar = QPushButton(objectName="chico")
        editar.setFlat(True)
        editar.setIcon(iconos.icono("mdi6.pencil", tema.TENUE))
        editar.setToolTip("Cambiar o quitar")
        editar.clicked.connect(lambda _=False, o=meta.objeto: self._editar(o))
        f.addWidget(editar)
        return fila

    def _editar(self, objeto: str):
        if DialogoMeta(self, objeto).exec_():
            self.pintar()

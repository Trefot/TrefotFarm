"""Metas de material en la interfaz, sin ventanas: la fila "Metas" (los materiales de un contenido, cada
uno una vez y sin %) y la franja que se abre debajo al tocar uno (tengo / quiero, donde sale mas).
Inicio usa las dos; Farmear, la fila (al tocar un material lleva a Inicio con su franja abierta)."""

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QSpinBox, QVBoxLayout, QWidget

from lumen import metas, premios
from lumen.gui import iconos, tema
from lumen.modos import MODOS

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


def icono(objeto: str, tam: int) -> QPixmap:
    pix = QPixmap(str(premios.ICONOS / f"{objeto}.png"))
    if pix.isNull():
        return iconos.pixmap("mdi6.help-box", tam, tema.TENUE)
    return pix.scaled(tam, tam, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def materiales(id_destino: str) -> list[premios.Premio]:
    """Lo que puede dar un destino, cada objeto una sola vez (en el orden de la tabla)."""
    vistos, salida = set(), []
    for p in premios.de(id_destino):
        if p.objeto not in vistos:
            vistos.add(p.objeto)
            salida.append(p)
    return salida


def texto_media(id_destino: str, objeto: str) -> str:
    """'≈2 por victoria' o '1 de cada 20 victorias' (en vez del % de la tabla)."""
    media = premios.esperado(id_destino, objeto)
    if media >= 0.95:
        return f"≈{media:.1f}".replace(".", ",").replace(",0", "") + " por victoria"
    return f"1 de cada {max(2, round(1 / media))} victorias" if media > 0 else ""


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


class FilaMateriales(QWidget):
    """'Metas': los materiales de un destino. Con meta: borde dorado, barrita y '12/40'."""

    tocado = pyqtSignal(str)  # objeto

    def __init__(self, tam: int, nombre_casilla: str, centrar: bool, titulo_arriba: bool = False):
        super().__init__()
        self.tam, self.nombre_casilla = tam, nombre_casilla
        capa = QVBoxLayout(self) if titulo_arriba else QHBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(2 if titulo_arriba else 8)
        self.titulo = QLabel("Metas", objectName="tenue")
        self.titulo.setToolTip("Toca un material para ponerte una meta")
        if centrar:
            capa.addStretch()
        capa.addWidget(self.titulo)
        self.fila = QHBoxLayout()
        self.fila.setSpacing(4 if tam < 40 else 8)
        capa.addLayout(self.fila)
        if centrar:
            capa.addStretch()
        self.objetos: list[str] = []

    def pintar(self, id_destino: str, todas: list[metas.Meta], abierto: str | None = None):
        while self.fila.count():
            w = self.fila.takeAt(0).widget()
            if w:
                w.deleteLater()
        lista = materiales(id_destino)
        self.objetos = [p.objeto for p in lista]
        self.titulo.setVisible(bool(lista))
        for p in lista:
            self.fila.addWidget(self._casilla(id_destino, p, metas.de(p.objeto, todas), p.objeto == abierto))

    def _casilla(self, id_destino: str, p: premios.Premio, meta: metas.Meta | None, abierta: bool) -> QFrame:
        casilla = QFrame(objectName=self.nombre_casilla)
        casilla.setCursor(Qt.PointingHandCursor)
        capa = QVBoxLayout(casilla)
        capa.setContentsMargins(3, 3, 3, 2)
        capa.setSpacing(1)
        dibujo = QLabel(alignment=Qt.AlignCenter)
        dibujo.setPixmap(icono(p.objeto, self.tam))
        capa.addWidget(dibujo)
        media = texto_media(id_destino, p.objeto)
        ayuda = f"<b>{p.nombre}</b><br>{p.descripcion}" + (f"<br><i>{media}</i>" if media else "")
        cuenta = QLabel(alignment=Qt.AlignCenter)
        cuenta.setFixedHeight(14)  # mismo alto con y sin meta
        if meta:
            color = tema.OK if meta.completa else tema.ACENTO
            capa.addWidget(barra(meta.actual, meta.quiero, 4, self.tam), 0, Qt.AlignHCenter)
            cuenta.setText(f"{meta.actual}/{meta.quiero}")
            cuenta.setStyleSheet(f"color: {color}; font-weight: 700; font-size: 8pt;")
            borde = f"2px solid {color}"
            ayuda = f"<b>Meta: {meta.actual} de {meta.quiero}</b><br>" + ayuda
        else:
            capa.addSpacing(5)
            borde = f"2px solid {tema.ACENTO}" if abierta else ""
            ayuda += "<br>Toca para ponerte una meta."
        capa.addWidget(cuenta)
        if borde:
            casilla.setStyleSheet(f"QFrame#{self.nombre_casilla} {{ border: {borde}; }}")
        casilla.setToolTip(ayuda)
        casilla.mousePressEvent = lambda _e, o=p.objeto: self.tocado.emit(o)
        return casilla


class EditorMeta(QFrame):
    """La franja bajo la fila: tengo / quiero del material tocado, donde sale mas, ir a farmearla y quitar."""

    cambiado = pyqtSignal()  # se creo, cambio o quito la meta
    cerrado = pyqtSignal()
    ir = pyqtSignal(str)  # id del destino donde mas sale

    def __init__(self):
        super().__init__(objectName="seccion")
        self.objeto: str | None = None
        capa = QHBoxLayout(self)
        capa.setContentsMargins(12, 8, 8, 8)
        capa.setSpacing(10)
        self.dibujo = QLabel()
        capa.addWidget(self.dibujo)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        self.nombre = QLabel()
        self.donde = QLabel(objectName="tenue", wordWrap=True)
        textos.addWidget(self.nombre)
        textos.addWidget(self.donde)
        capa.addLayout(textos, 1)
        self.tengo = QSpinBox(maximum=999_999, prefix="Tengo ")
        self.quiero = QSpinBox(minimum=1, maximum=999_999, prefix="Quiero ")
        for spin in (self.tengo, self.quiero):
            spin.setMinimumWidth(120)
            spin.valueChanged.connect(self._cambiado)
            capa.addWidget(spin)
        self.b_crear = QPushButton(" Crear meta", objectName="primario")
        self.b_crear.setIcon(iconos.icono(ICONO, tema.SOBRE_ACENTO))
        self.b_crear.clicked.connect(self._guardar_cifras)
        capa.addWidget(self.b_crear)
        self.b_ir = QPushButton(" Ir a farmearla", objectName="chico")
        self.b_ir.setIcon(iconos.icono("jugar", tema.ACENTO))
        self.b_ir.setToolTip("Elige donde más sale y deja puesto «Meta»: el bot para al completarla")
        self.b_ir.clicked.connect(self._ir)
        capa.addWidget(self.b_ir)
        self.b_quitar = QPushButton(objectName="chico")
        self.b_quitar.setIcon(iconos.icono("mdi6.delete-outline", tema.TEXTO))
        self.b_quitar.setToolTip("Quitar la meta")
        self.b_quitar.clicked.connect(self._quitar)
        capa.addWidget(self.b_quitar)
        cerrar = QPushButton(objectName="chico")
        cerrar.setFlat(True)
        cerrar.setIcon(iconos.icono("mdi6.close", tema.TENUE))
        cerrar.setToolTip("Cerrar")
        cerrar.clicked.connect(self.cerrar)
        capa.addWidget(cerrar)
        self._guardar = QTimer(self, singleShot=True, interval=GUARDAR_MS, timeout=self._guardar_cifras)
        self.hide()

    def abrir(self, objeto: str):
        self.objeto = objeto
        self.dibujo.setPixmap(icono(objeto, 40))
        self._pintar(metas.de(objeto, metas.cargar(fresco=True)))
        self.show()
        self.quiero.setFocus()
        self.quiero.selectAll()

    def cerrar(self):
        self._guardar.stop()
        self.objeto = None
        self.hide()
        self.cerrado.emit()

    def _pintar(self, meta: metas.Meta | None):
        info = premios.info(self.objeto)
        mejor = metas.mejor_destino(self.objeto)
        nueva = meta is None
        if nueva:  # aun no es meta: unas 10 victorias de botin como punto de partida
            meta = metas.Meta(self.objeto, 0, max(10, round(mejor[1] * 10)) if mejor else 10, 0)
        self.nombre.setText(f"<b>{info.get('nombre', self.objeto)}</b>" + ("" if nueva else f"  ·  {meta.actual} / {meta.quiero}"))
        self.donde.setText(estimacion(meta))
        for spin, valor in ((self.tengo, meta.actual), (self.quiero, meta.quiero)):
            if nueva or not spin.hasFocus():
                spin.blockSignals(True)
                spin.setValue(valor)
                spin.blockSignals(False)
        self.b_crear.setVisible(nueva)
        self.b_quitar.setVisible(not nueva)
        self.b_ir.setVisible(not nueva and not meta.completa and mejor is not None)

    def _cambiado(self):
        if self.b_crear.isHidden():  # una meta que ya existe se guarda sola
            self._guardar.start()
        else:
            self.donde.setText(estimacion(metas.Meta(self.objeto, self.tengo.value(), self.quiero.value(), 0)))

    def _guardar_cifras(self):
        if self.objeto is None:
            return
        metas.poner(self.objeto, self.tengo.value(), self.quiero.value())
        self._pintar(metas.de(self.objeto, metas.cargar(fresco=True)))
        self.cambiado.emit()

    def _quitar(self):
        metas.quitar(self.objeto)
        self.cambiado.emit()
        self.cerrar()

    def _ir(self):
        mejor = metas.mejor_destino(self.objeto)
        if mejor:
            self.ir.emit(mejor[0])

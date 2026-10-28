"""Pagina Personajes: galeria como en el juego. A color los que tienes, en gris los que no.

El jugador solo marca si tiene cada personaje (clic en su tarjeta). Las fichas, cartas y retratos
vienen en la base fija del bot; se editan en el Editor de personajes (modo administrador).
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from lumen import config
from lumen import personajes as P
from lumen.gui import iconos, tema
from lumen.gui.comun import Pagina
from lumen.modos import MODOS

ANCHO_TARJETA = 138
HUECO = 12
COLOR_ATRIBUTO = {"rojo": "#e05a4f", "verde": "#4cc38a", "azul": "#4f8fe0", "claro": "#e6c84c", "oscuro": "#a06ad8",
                  "sin definir": tema.TENUE}


def _en_gris(pix: QPixmap) -> QPixmap:
    img = pix.toImage().convertToFormat(QImage.Format_Grayscale8)
    return QPixmap.fromImage(img)


class TarjetaPersonaje(QFrame):
    """Retrato con nombre y atributo. Clic = lo tengo / no lo tengo."""

    cambiado = pyqtSignal(str, bool)

    def __init__(self, pj: P.Personaje, usado_en: list[str]):
        super().__init__(objectName="tarjeta_pj")
        self.pj = pj
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(ANCHO_TARJETA, 222)
        self.usado_en = usado_en
        capa = QVBoxLayout(self)
        capa.setContentsMargins(8, 8, 8, 8)
        capa.setSpacing(4)

        self.foto = QLabel(alignment=Qt.AlignCenter)
        self.foto.setFixedSize(120, 140)
        self.foto.setObjectName("foto_pj")
        self.pix = None
        ruta = pj.ruta_cara()
        if ruta.is_file():
            pix = QPixmap(str(ruta))
            if pix.width() >= pix.height():  # icono cuadrado de la lista de Heroes: entero
                pix = pix.scaled(120, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            else:  # retrato alargado de la pantalla del equipo: recortado al centro
                pix = pix.scaled(120, 140, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                pix = pix.copy((pix.width() - 120) // 2, 0, 120, 140)
            self.pix = pix
        else:
            self.foto.setPixmap(iconos.pixmap("mdi6.account-question", 56, tema.TENUE))
        capa.addWidget(self.foto, 0, Qt.AlignHCenter)

        nombre = QLabel(pj.nombre, alignment=Qt.AlignCenter, wordWrap=True)
        nombre.setObjectName("nombre_pj")
        capa.addWidget(nombre)
        fila = QHBoxLayout()
        fila.setSpacing(4)
        punto = QLabel("●")
        punto.setStyleSheet(f"color: {COLOR_ATRIBUTO.get(pj.color, tema.TENUE)}; font-size: 11pt;")
        fila.addStretch()
        fila.addWidget(punto)
        fila.addWidget(QLabel(P.NOMBRE_COLOR.get(pj.color, "?"), objectName="tenue"))
        fila.addStretch()
        capa.addLayout(fila)
        if not pj.tiene_datos:
            capa.addWidget(QLabel("Sin datos aún", objectName="tenue", alignment=Qt.AlignCenter))
        self.poner_tengo(pj.tengo)

    def poner_tengo(self, tengo: bool):
        """A color si lo tienes, en gris si no (sin rehacer la tarjeta)."""
        self.pj.tengo = tengo
        if self.pix is not None:
            self.foto.setPixmap(self.pix if tengo else _en_gris(self.pix))
        self.setToolTip(("Lo tienes. " if tengo else "No lo tienes. ") + "Clic para cambiar."
                        + (f"\nSe usa en: {', '.join(self.usado_en)}" if self.usado_en else ""))
        self.setProperty("tengo", tengo)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, evento):
        if evento.button() == Qt.LeftButton:
            self.cambiado.emit(self.pj.id, not self.pj.tengo)
        super().mousePressEvent(evento)


class PaginaPersonajes(Pagina):
    titulo = "Personajes"
    subtitulo = "Toca los que tienes. A color = lo tienes."

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.b_editar = QPushButton("  Editar base", objectName="chico")
        self.b_editar.setIcon(iconos.icono("mdi6.database-edit", tema.TEXTO))
        self.b_editar.clicked.connect(lambda: app.navegar("editor"))
        self.acciones.addWidget(self.b_editar)

        barra = QHBoxLayout()
        self.buscar = QLineEdit(placeholderText="Buscar personaje...")
        self.buscar.setClearButtonEnabled(True)
        self.buscar.setMaximumWidth(280)
        self.buscar.textChanged.connect(self._pintar)
        barra.addWidget(self.buscar)
        self.filtro = QButtonGroup(self, exclusive=True)
        for i, (texto, ayuda) in enumerate((("Todos", ""), ("Los tengo", ""), ("Me faltan", ""),
                                            ("En equipos", "Los que salen en algún equipo recomendado"))):
            b = QPushButton(texto, objectName="chip", checkable=True)
            b.setChecked(i == 0)
            b.setToolTip(ayuda)
            self.filtro.addButton(b, i)
            barra.addWidget(b)
        self.filtro.buttonClicked.connect(lambda _: self._pintar())
        barra.addSpacing(10)
        # Atributo: un punto de color por cada uno (se pueden quitar todos = sin filtro)
        self.atributos = QButtonGroup(self, exclusive=False)
        for color in ("rojo", "verde", "azul", "claro", "oscuro"):
            b = QPushButton("●", objectName="chip", checkable=True)
            b.setFixedWidth(34)
            b.setToolTip(P.NOMBRE_COLOR[color])
            b.setStyleSheet(f"QPushButton {{ color: {COLOR_ATRIBUTO[color]}; font-size: 13pt; padding: 0; }}")
            b.setProperty("color", color)
            self.atributos.addButton(b)
            barra.addWidget(b)
        self.atributos.buttonClicked.connect(lambda _: self._pintar())
        barra.addStretch()
        self.contador = QLabel(objectName="titulo_seccion")
        barra.addWidget(self.contador)
        self.cuerpo.addLayout(barra)

        self.zona = QWidget()
        self.rejilla = QGridLayout(self.zona)
        self.rejilla.setSpacing(HUECO)
        self.rejilla.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.desplazar = QScrollArea(widgetResizable=True)
        self.desplazar.setWidget(self.zona)
        self.cuerpo.addWidget(self.desplazar, 1)
        self.tarjetas: dict[str, TarjetaPersonaje] = {}
        self.columnas = 0
        self.al_mostrar()

    def al_mostrar(self):
        self.b_editar.setVisible(bool(config.obtener("modo_admin")))
        self.biblioteca = P.cargar()
        self._construir()
        self._pintar()

    def _construir(self):
        """Una tarjeta por personaje (se hacen una vez; filtrar solo las coloca o las esconde)."""
        for t in self.tarjetas.values():
            t.setParent(None)
        from lumen.gui.paginas.equipos import cargar_equipos

        self.en_equipos = {pid for clave, lista in cargar_equipos().items() if not clave.startswith("_")
                           for datos in lista or [] for pid in (datos.get("personajes") or [])}
        self.tarjetas = {}
        for pj in self.biblioteca.values():
            usado = [m.titulo_juego or m.nombre for m in MODOS.values() if getattr(m, "equipo", None) and pj.id in m.equipo.orden]
            t = TarjetaPersonaje(pj, usado)
            t.cambiado.connect(self._cambiar)
            t.hide()
            self.tarjetas[pj.id] = t
        self.orden = sorted(self.biblioteca.values(), key=lambda p: (not p.tengo, not p.tiene_datos, p.nombre.lower()))

    def _columnas_que_caben(self) -> int:
        ancho = self.desplazar.viewport().width() - 2 * HUECO
        return max(1, (ancho + HUECO) // (ANCHO_TARJETA + HUECO))

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        if self.tarjetas and self._columnas_que_caben() != self.columnas:
            self._pintar()

    def _pintar(self):
        while self.rejilla.count():
            self.rejilla.takeAt(0)
        texto = self.buscar.text().strip().lower()
        filtro = self.filtro.checkedId()
        colores = {b.property("color") for b in self.atributos.buttons() if b.isChecked()}
        self.columnas = self._columnas_que_caben()
        n = 0
        for pj in self.orden:
            t = self.tarjetas[pj.id]
            visible = (not texto or texto in pj.nombre.lower()) \
                and not (filtro == 1 and not pj.tengo) and not (filtro == 2 and pj.tengo) \
                and not (filtro == 3 and pj.id not in self.en_equipos) \
                and (not colores or pj.color in colores)
            t.setVisible(visible)
            if visible:
                self.rejilla.addWidget(t, n // self.columnas, n % self.columnas)
                n += 1
        tengo = sum(1 for p in self.biblioteca.values() if p.tengo)
        self.contador.setText(f"Tienes {tengo} de {len(self.biblioteca)}")

    def _cambiar(self, pid: str, tengo: bool):
        P.marcar_tengo(pid, tengo)
        for modo in MODOS.values():
            if getattr(modo, "equipo", None):
                modo.equipo.recargar()
        self.tarjetas[pid].poner_tengo(tengo)  # se queda en su sitio: el orden cambia al volver a la pagina
        filtro = self.filtro.checkedId()
        if filtro in (1, 2):  # con "Los tengo" / "Me faltan" ya no le toca estar
            self._pintar()
        tengo_total = sum(1 for p in self.biblioteca.values() if p.tengo)
        self.contador.setText(f"Tienes {tengo_total} de {len(self.biblioteca)}")
        self.app.refrescar_insignias()

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

from trefot import config
from trefot import personajes as P
from trefot.gui import iconos, tema
from trefot.gui.comun import Pagina
from trefot.modos import MODOS

COLUMNAS = 6
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
        self.setFixedSize(138, 222)
        self.setToolTip(("Lo tienes. " if pj.tengo else "No lo tienes. ") + "Clic para cambiar."
                        + (f"\nSe usa en: {', '.join(usado_en)}" if usado_en else ""))
        capa = QVBoxLayout(self)
        capa.setContentsMargins(8, 8, 8, 8)
        capa.setSpacing(4)

        foto = QLabel(alignment=Qt.AlignCenter)
        foto.setFixedSize(120, 140)
        foto.setObjectName("foto_pj")
        ruta = pj.ruta(P.RETRATO)
        if ruta.is_file():
            pix = QPixmap(str(ruta)).scaled(120, 140, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            pix = pix.copy((pix.width() - 120) // 2, 0, 120, 140)
            foto.setPixmap(pix if pj.tengo else _en_gris(pix))
        else:
            foto.setPixmap(iconos.pixmap("mdi6.account-question", 56, tema.TENUE))
        capa.addWidget(foto, 0, Qt.AlignHCenter)

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

        self.setProperty("tengo", pj.tengo)

    def mousePressEvent(self, evento):
        if evento.button() == Qt.LeftButton:
            self.cambiado.emit(self.pj.id, not self.pj.tengo)
        super().mousePressEvent(evento)


class PaginaPersonajes(Pagina):
    titulo = "Personajes"
    subtitulo = "Marca los personajes que tienes en el juego: haz clic en su tarjeta. A color = lo tienes."

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
        for i, texto in enumerate(("Todos", "Los tengo", "Me faltan")):
            b = QPushButton(texto, objectName="chip", checkable=True)
            b.setChecked(i == 0)
            self.filtro.addButton(b, i)
            barra.addWidget(b)
        self.filtro.buttonClicked.connect(lambda _: self._pintar())
        barra.addStretch()
        self.contador = QLabel(objectName="titulo_seccion")
        barra.addWidget(self.contador)
        self.cuerpo.addLayout(barra)

        self.zona = QWidget()
        self.rejilla = QGridLayout(self.zona)
        self.rejilla.setSpacing(12)
        self.rejilla.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        desplazar = QScrollArea(widgetResizable=True)
        desplazar.setWidget(self.zona)
        self.cuerpo.addWidget(desplazar, 1)
        self.al_mostrar()

    def al_mostrar(self):
        self.b_editar.setVisible(bool(config.obtener("modo_admin")))
        self.biblioteca = P.cargar()
        self._pintar()

    def _pintar(self):
        while self.rejilla.count():
            w = self.rejilla.takeAt(0).widget()
            if w:
                w.setParent(None)
        texto = self.buscar.text().strip().lower()
        filtro = self.filtro.checkedId()
        lista = sorted(self.biblioteca.values(), key=lambda p: (not p.tengo, not p.tiene_datos, p.nombre.lower()))
        n = 0
        for pj in lista:
            if texto and texto not in pj.nombre.lower():
                continue
            if (filtro == 1 and not pj.tengo) or (filtro == 2 and pj.tengo):
                continue
            usado = [m.titulo_juego or m.nombre for m in MODOS.values() if getattr(m, "equipo", None) and pj.id in m.equipo.orden]
            t = TarjetaPersonaje(pj, usado)
            t.cambiado.connect(self._cambiar)
            self.rejilla.addWidget(t, n // COLUMNAS, n % COLUMNAS)
            n += 1
        tengo = sum(1 for p in self.biblioteca.values() if p.tengo)
        self.contador.setText(f"Tienes {tengo} de {len(self.biblioteca)}")

    def _cambiar(self, pid: str, tengo: bool):
        P.marcar_tengo(pid, tengo)
        for modo in MODOS.values():
            if getattr(modo, "equipo", None):
                modo.equipo.recargar()
        self.al_mostrar()
        self.app.refrescar_insignias()

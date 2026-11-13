"""Pagina Personajes: galeria como en el juego. A color los que tienes, en gris los que no.

El jugador solo marca si tiene cada personaje (clic en su tarjeta). Las fichas, cartas y retratos
vienen en la base fija del bot; se editan en el Editor de personajes (modo administrador).
"""

import html
import re

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from lumen import personajes as P
from lumen.gui import iconos, tema
from lumen.gui.comun import Pagina
from lumen.modos import MODOS

ANCHO_TARJETA = 178
FOTO = (160, 185)  # el artwork entero (sin el texto del juego) cabe casi justo: lo eligio el usuario (2026-10-29)
HUECO = 12
COLOR_ATRIBUTO = {"rojo": "#e05a4f", "verde": "#4cc38a", "azul": "#4f8fe0", "claro": "#e6c84c", "oscuro": "#a06ad8",
                  "sin definir": tema.TENUE}


def _en_gris(pix: QPixmap) -> QPixmap:
    """En gris, conservando la transparencia (las esquinas redondeadas de los cuadros de Inicio y Equipos)."""
    original = pix.toImage().convertToFormat(QImage.Format_ARGB32)
    gris = original.convertToFormat(QImage.Format_Grayscale8).convertToFormat(QImage.Format_ARGB32)
    gris.setAlphaChannel(original.convertToFormat(QImage.Format_Alpha8))
    return QPixmap.fromImage(gris)


def _firma(pj: P.Personaje) -> tuple:
    """Lo que cambia la tarjeta de un personaje (si no cambia, se reutiliza la de la visita anterior)."""
    def fecha(ruta):
        try:
            return ruta.stat().st_mtime
        except OSError:
            return 0

    return pj.nombre, pj.color, pj.tiene_datos, fecha(pj.ruta_artwork()), fecha(pj.ruta_cara())


def texto_juego(texto: str) -> str:
    """Texto de 7dshub a HTML: los colores del juego ([RRGGBB]texto[-]) se pintan y los saltos de linea se ven."""
    t = html.escape(texto or "")
    t = re.sub(r"\[([0-9A-Fa-f]{6})\](.*?)\[-\]", r'<span style="color:#\1">\2</span>', t, flags=re.S)
    t = re.sub(r"\[[0-9A-Fa-f]{6}\]|\[-\]", "", t)
    return t.replace("\\n", "<br>").replace("\n", "<br>")  # 7dshub trae los saltos escritos como \n


NOMBRES_PERFIL = {"edad": "Edad", "altura": "Altura", "peso": "Peso", "cumpleanos": "Cumpleaños", "sangre": "Sangre",
                  "voz": "Voz (japonés)"}


class DialogoFicha(QDialog):
    """Todo lo que se sabe de un heroe, para leerlo: sus cartas con lo que hacen en cada rango, la ulti, la pasiva
    unica, el talento, la reliquia y su perfil (datos de 7dshub.com). Lo pidio el usuario (2026-11-09)."""

    def __init__(self, pj: P.Personaje, padre=None):
        super().__init__(padre)
        datos = P.ficha(pj.id)
        self.setWindowTitle(pj.nombre)
        self.setMinimumSize(600, 680)
        exterior = QVBoxLayout(self)
        cabecera = QHBoxLayout()
        cara = QLabel()
        ruta, _ = pj.rostro()
        if ruta and ruta.is_file():
            cara.setPixmap(QPixmap(str(ruta)).scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        cabecera.addWidget(cara)
        titulos = QVBoxLayout()
        clave = (P._leer_yaml(P.BASE).get(pj.id) or {}).get("clave", "")
        titulos.addWidget(QLabel(pj.nombre, objectName="titulo_seccion", wordWrap=True))
        if clave and clave != pj.nombre:
            titulos.addWidget(QLabel(clave, objectName="tenue", wordWrap=True))
        color = QLabel(f"<span style='color:{COLOR_ATRIBUTO.get(pj.color, tema.TENUE)}'>●</span> "
                       f"{P.NOMBRE_COLOR.get(pj.color, '?')}")
        titulos.addWidget(color)
        titulos.addStretch()
        cabecera.addLayout(titulos, 1)
        exterior.addLayout(cabecera)

        zona = QWidget()
        capa = QVBoxLayout(zona)
        capa.setSpacing(12)
        if not datos:
            capa.addWidget(QLabel("Todavía no hay ficha de este personaje.", objectName="tenue"))
        for carta, titulo in (("skill_1", "Habilidad 1"), ("skill_2", "Habilidad 2"), ("ulti", "Ulti")):
            info = datos.get(carta)
            if not info:
                continue
            fila = QHBoxLayout()
            img = QLabel()
            ruta = pj.ruta_hub(carta)
            if not ruta.is_file():
                ruta = pj.ruta_ficha(carta)
            if ruta.is_file():
                img.setPixmap(QPixmap(str(ruta)).scaled(90, 148, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            fila.addWidget(img, 0, Qt.AlignTop)
            if "rangos" in info:
                cuerpo = "".join(f"<p><b>Rango {i}</b><br>{texto_juego(t)}</p>" for i, t in enumerate(info["rangos"], 1))
            else:
                cuerpo = f"<p>{texto_juego(info.get('texto', ''))}</p>"
            fila.addWidget(self._texto(f"<b>{titulo}: {html.escape(info['nombre'])}</b>{cuerpo}"), 1)
            capa.addLayout(fila)
        for clave_, titulo in (("pasiva", "Pasiva única"), ("talento", "Talento"), ("reliquia", "Reliquia sagrada")):
            info = datos.get(clave_)
            if info and (info.get("nombre") or info.get("texto")):
                capa.addWidget(self._texto(f"<b>{titulo}: {html.escape(info.get('nombre', ''))}</b>"
                                           f"<p>{texto_juego(info.get('texto', ''))}</p>"))
        if datos.get("perfil"):
            filas = "".join(f"<tr><td><b>{NOMBRES_PERFIL.get(k, k)}</b>&nbsp;&nbsp;</td><td>{html.escape(str(v))}</td></tr>"
                            for k, v in datos["perfil"].items())
            capa.addWidget(self._texto(f"<b>Perfil</b><table>{filas}</table>"))
        capa.addWidget(QLabel("Datos e imágenes: 7dshub.com", objectName="tenue"))
        capa.addStretch()
        desplazar = QScrollArea(widgetResizable=True)
        desplazar.setWidget(zona)
        exterior.addWidget(desplazar, 1)
        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.accept)
        exterior.addWidget(cerrar, 0, Qt.AlignRight)

    @staticmethod
    def _texto(contenido: str) -> QLabel:
        etiqueta = QLabel(contenido, wordWrap=True)
        etiqueta.setTextFormat(Qt.RichText)
        etiqueta.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return etiqueta


class TarjetaPersonaje(QFrame):
    """Retrato con nombre y atributo. Clic = lo tengo / no lo tengo."""

    cambiado = pyqtSignal(str, bool)

    def __init__(self, pj: P.Personaje, usado_en: list[str], padre=None):
        # Con padre desde el principio: una tarjeta sin padre que se hace visible es una ventana suelta
        # (eso eran las "ventanitas" que salian al abrir la pagina).
        super().__init__(padre, objectName="tarjeta_pj")
        self.pj = pj
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(ANCHO_TARJETA, FOTO[1] + 92)  # sitio para nombres largos en 2-3 lineas
        self.usado_en = usado_en
        capa = QVBoxLayout(self)
        capa.setContentsMargins(8, 8, 8, 8)
        capa.setSpacing(4)

        self.foto = QLabel(alignment=Qt.AlignCenter)
        self.foto.setFixedSize(*FOTO)
        self.foto.setObjectName("foto_pj")
        self.pix = None
        self.cargada = False  # la imagen se lee al verse la tarjeta por primera vez (ver paintEvent)
        capa.addWidget(self.foto, 0, Qt.AlignHCenter)
        # Boton para leer la ficha (el clic en la tarjeta sigue siendo "lo tengo / no lo tengo")
        self.info = QToolButton(self)
        self.info.setText("ⓘ")
        self.info.setToolTip("Ver su ficha: cartas, pasiva, talento, reliquia...")
        self.info.setCursor(Qt.PointingHandCursor)
        self.info.setStyleSheet("QToolButton { background: rgba(0,0,0,150); color: white; border-radius: 11px;"
                                " font-size: 11pt; padding: 0 5px; }")
        self.info.move(ANCHO_TARJETA - 34, 10)
        self.info.clicked.connect(self.abrir_ficha)

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

    def _cargar_foto(self):
        self.cargada = True
        w, h = FOTO
        artwork = self.pj.ruta_artwork()
        ruta = self.pj.ruta_cara()
        if ruta.name == P.ICONO_HUB:  # el icono de 7dshub, entero (lo eligio el usuario, 2026-11-08)
            self.pix = QPixmap(str(ruta)).scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        elif artwork.is_file():  # la ilustracion entera, sin el texto del juego de abajo
            pix = QPixmap(str(artwork))
            pix = pix.copy(0, 0, int(pix.width() * P.ANCHO_SIN_BORDE), int(pix.height() * P.ALTO_SIN_TEXTO))
            self.pix = pix.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        elif ruta.is_file():
            pix = QPixmap(str(ruta))
            if pix.width() >= pix.height():  # icono cuadrado de la lista de Heroes: entero
                pix = pix.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            else:  # retrato alargado de la pantalla del equipo: recortado al centro
                pix = pix.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                pix = pix.copy((pix.width() - w) // 2, 0, w, h)
            self.pix = pix
        else:
            self.foto.setPixmap(iconos.pixmap("mdi6.account-question", 56, tema.TENUE))
        self._poner_foto()

    def paintEvent(self, evento):
        # Solo se pintan las tarjetas que se ven en la pagina: asi se leen unas pocas imagenes al abrirla y
        # el resto al bajar, en vez de las mas de 400 de golpe.
        if not self.cargada:
            self._cargar_foto()
        super().paintEvent(evento)

    def _poner_foto(self):
        if self.pix is not None:
            self.foto.setPixmap(self.pix if self.pj.tengo else _en_gris(self.pix))

    def poner_tengo(self, tengo: bool):
        """A color si lo tienes, en gris si no (sin rehacer la tarjeta)."""
        self.pj.tengo = tengo
        if self.cargada:
            self._poner_foto()
        self.setToolTip(("Lo tienes. " if tengo else "No lo tienes. ") + "Clic para cambiar."
                        + (f"\nSe usa en: {', '.join(self.usado_en)}" if self.usado_en else ""))
        self.setProperty("tengo", tengo)
        self.style().unpolish(self)
        self.style().polish(self)

    def abrir_ficha(self):
        DialogoFicha(self.pj, self.window()).exec_()

    def mousePressEvent(self, evento):
        if evento.button() == Qt.RightButton:  # clic derecho: la ficha
            self.abrir_ficha()
            return
        if evento.button() == Qt.LeftButton:
            self.cambiado.emit(self.pj.id, not self.pj.tengo)
        super().mousePressEvent(evento)


class PaginaPersonajes(Pagina):
    titulo = "Personajes"
    subtitulo = "Toca los que tienes (a color = lo tienes). ⓘ o clic derecho: su ficha. Más rápido: «Marcar todos»."

    def __init__(self, app):
        super().__init__()
        self.app = app
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
        # Con ~365 personajes, marcarlos uno a uno cansa (lo pidio un probador, 2026-11-08): se marcan todos
        # los que se ven (con la busqueda y los filtros) y luego se quitan los que faltan.
        for texto, tengo, ayuda in (("Marcar todos", True, "Marca como tuyos todos los que se ven ahora "
                                                         "(con la búsqueda y los filtros). Luego quita los que te faltan."),
                                    ("Quitar todos", False, "Desmarca todos los que se ven ahora (con la búsqueda y los filtros).")):
            b = QPushButton(texto, objectName="chip")
            b.setToolTip(ayuda)
            b.clicked.connect(lambda _=False, t=tengo: self._marcar_visibles(t))
            barra.addWidget(b)
        barra.addSpacing(10)
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
        self.biblioteca = {}  # se carga al abrir la pagina (al_mostrar): construirla al arrancar tardaba ~1,2 s
        self.orden = []

    def al_mostrar(self):
        self.biblioteca = P.cargar()
        self._construir()
        self._pintar()

    def _construir(self):
        """Una tarjeta por personaje. Se guardan entre visitas: solo se rehace la de un personaje nuevo o que
        cambio (nombre, atributo, datos o sus imagenes); filtrar solo las coloca o las esconde."""
        from lumen.gui.paginas.equipos import cargar_equipos

        self.en_equipos = {pid for clave, lista in cargar_equipos().items() if not clave.startswith("_")
                           for datos in lista or [] for pid in (datos.get("personajes") or [])}
        anteriores, self.tarjetas = self.tarjetas, {}
        for pj in self.biblioteca.values():
            firma = _firma(pj)
            t = anteriores.pop(pj.id, None)
            if t is not None and t.firma == firma:
                t.pj = pj
                t.poner_tengo(pj.tengo)
            else:
                if t is not None:
                    t.deleteLater()
                usado = [m.titulo_juego or m.nombre for m in MODOS.values()
                         if getattr(m, "equipo", None) and pj.id in m.equipo.orden]
                t = TarjetaPersonaje(pj, usado, self.zona)
                t.firma = firma
                t.cambiado.connect(self._cambiar)
                t.hide()
            self.tarjetas[pj.id] = t
        for t in anteriores.values():  # personajes que ya no estan
            t.deleteLater()
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
        self.zona.setUpdatesEnabled(False)  # se recoloca todo de una vez, sin repintar tarjeta a tarjeta
        for pj in self.orden:
            t = self.tarjetas[pj.id]
            visible = (not texto or texto in pj.nombre.lower()) \
                and not (filtro == 1 and not pj.tengo) and not (filtro == 2 and pj.tengo) \
                and not (filtro == 3 and pj.id not in self.en_equipos) \
                and (not colores or pj.color in colores)
            if visible:
                self.rejilla.addWidget(t, n // self.columnas, n % self.columnas)
                n += 1
            t.setVisible(visible)
        self.zona.setUpdatesEnabled(True)
        tengo = sum(1 for p in self.biblioteca.values() if p.tengo)
        self.contador.setText(f"Tienes {tengo} de {len(self.biblioteca)}")

    def visibles(self) -> list[str]:
        return [pj.id for pj in self.orden if self.tarjetas[pj.id].isVisibleTo(self.zona)]

    def _marcar_visibles(self, tengo: bool):
        pids = [pid for pid in self.visibles() if self.biblioteca[pid].tengo != tengo]
        if not pids:
            return
        pregunta = (f"¿Marcar {len(pids)} personajes como tuyos? Luego puedes quitar los que te falten."
                    if tengo else f"¿Quitar {len(pids)} personajes de los tuyos?")
        if QMessageBox.question(self, "Personajes", pregunta) != QMessageBox.Yes:
            return
        self.aplicar_varios(pids, tengo)

    def aplicar_varios(self, pids: list[str], tengo: bool):
        P.marcar_varios(pids, tengo)
        for pid in pids:
            self.biblioteca[pid].tengo = tengo
            self.tarjetas[pid].poner_tengo(tengo)
        for modo in MODOS.values():
            if getattr(modo, "equipo", None):
                modo.equipo.recargar()
        self._pintar()
        self.app.refrescar_insignias()

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

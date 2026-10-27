"""Pagina Equipos: equipos recomendados por cada contenido, del mejor al mas dificil.

Los equipos vienen de lumen/datos/equipos.yaml (base fija que mantiene el administrador). Cada
equipo es una tarjeta desplegable: retratos (en gris los que no tienes), nivel, si el bot lo juega,
que te falta y como se juega.
"""

from pathlib import Path

import yaml
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from lumen import config
from lumen import personajes as P
from lumen.gui import iconos, tema
from lumen.gui.comun import Pagina
from lumen.gui.paginas.personajes import _en_gris
from lumen.modos import MODOS
from lumen.rutas import IMAGENES

ARCHIVO = Path(__file__).resolve().parents[2] / "datos" / "equipos.yaml"
NIVELES = {
    "recomendado": ("Recomendado", tema.OK),
    "bueno": ("Bueno", "#4f8fe0"),
    "alternativa": ("Alternativa", tema.AVISO),
}


def cargar_equipos() -> dict:
    if not ARCHIVO.is_file():
        return {}
    with ARCHIVO.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _retrato(pj: P.Personaje | None, nombre: str, tengo: bool, tam=(64, 84)) -> QWidget:
    caja = QWidget()
    capa = QVBoxLayout(caja)
    capa.setContentsMargins(0, 0, 0, 0)
    capa.setSpacing(2)
    foto = QLabel(alignment=Qt.AlignCenter)
    foto.setFixedSize(*tam)
    foto.setObjectName("foto_pj")
    ruta = pj.ruta(P.RETRATO) if pj else None
    if ruta and ruta.is_file():
        pix = QPixmap(str(ruta)).scaled(tam[0], tam[1], Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        pix = pix.copy((pix.width() - tam[0]) // 2, 0, tam[0], tam[1])
        foto.setPixmap(pix if tengo else _en_gris(pix))
    else:
        foto.setPixmap(iconos.pixmap("mdi6.account-question", 34, tema.TENUE))
    foto.setProperty("tengo", tengo)
    capa.addWidget(foto, 0, Qt.AlignHCenter)
    texto = QLabel(nombre, alignment=Qt.AlignCenter, wordWrap=True)
    texto.setFixedWidth(tam[0] + 22)
    texto.setStyleSheet(f"color: {tema.TEXTO if tengo else tema.TENUE}; font-size: 8.5pt;")
    capa.addWidget(texto, 0, Qt.AlignHCenter)
    return caja


class TarjetaEquipo(QFrame):
    """Un equipo recomendado: cabecera siempre visible y detalle desplegable."""

    def __init__(self, datos: dict, biblioteca: dict, abierto: bool):
        super().__init__(objectName="tarjeta_equipo")
        capa = QVBoxLayout(self)
        capa.setContentsMargins(14, 12, 14, 12)

        ids = datos.get("personajes") or []
        faltan = [pid for pid in ids if not (biblioteca.get(pid) and biblioteca[pid].tengo)]
        alternativas = datos.get("alternativas") or {}
        # Un hueco con alternativa cuenta como cubierto si tienes alguna de ellas.
        faltan = [pid for pid in faltan if not any(biblioteca.get(a) and biblioteca[a].tengo for a in alternativas.get(pid, []))]
        self.completo = not faltan

        cab = QHBoxLayout()
        nivel_texto, nivel_color = NIVELES.get(datos.get("nivel", ""), ("", tema.TENUE))
        nivel = QLabel(nivel_texto)
        nivel.setStyleSheet(f"background: {nivel_color}; color: {tema.FONDO}; border-radius: 9px; padding: 2px 10px; font-weight: 700;")
        cab.addWidget(nivel)
        cab.addWidget(QLabel(datos.get("nombre", ""), objectName="titulo_tarjeta"))
        if datos.get("bot"):
            bot = QLabel("  El bot lo juega")
            bot.setStyleSheet(f"color: {tema.ACENTO}; font-weight: 700;")
            cab.addWidget(bot)
        cab.addStretch()
        estado = QLabel()
        if self.completo:
            estado.setText(f"<span style='color:{tema.OK}'><b>Lo tienes completo</b></span>")
        else:
            nombres = [biblioteca[p].nombre if p in biblioteca else p for p in faltan]
            estado.setText(f"<span style='color:{tema.AVISO}'>Te falta: {', '.join(nombres)}</span>")
        cab.addWidget(estado)
        self.flecha = QPushButton(objectName="chico")
        self.flecha.setFlat(True)
        self.flecha.clicked.connect(self._alternar)
        cab.addWidget(self.flecha)
        capa.addLayout(cab)

        fila = QHBoxLayout()
        fila.setSpacing(10)
        for pid in ids:
            pj = biblioteca.get(pid)
            tengo = bool(pj and pj.tengo) or any(biblioteca.get(a) and biblioteca[a].tengo for a in alternativas.get(pid, []))
            nombre = pj.nombre if pj else pid
            if pid in alternativas:
                nombre += " (o " + " / ".join(biblioteca[a].nombre if a in biblioteca else a for a in alternativas[pid]) + ")"
            fila.addWidget(_retrato(pj, nombre, tengo))
        fila.addStretch()
        capa.addLayout(fila)

        self.detalle = QLabel(datos.get("notas", ""), wordWrap=True, objectName="tenue")
        self.detalle.setContentsMargins(4, 6, 4, 0)
        capa.addWidget(self.detalle)
        self.abierto = abierto
        self._mostrar()

    def _alternar(self):
        self.abierto = not self.abierto
        self._mostrar()

    def _mostrar(self):
        self.detalle.setVisible(self.abierto)
        self.flecha.setIcon(iconos.icono("mdi6.chevron-up" if self.abierto else "mdi6.chevron-down", tema.TEXTO))
        self.flecha.setToolTip("Ocultar detalles" if self.abierto else "Ver como se juega")

    def mousePressEvent(self, evento):
        self._alternar()
        super().mousePressEvent(evento)


class PaginaEquipos(Pagina):
    titulo = "Equipos"
    subtitulo = "Del mejor al más difícil."

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.selector = QHBoxLayout()
        self.grupo = QButtonGroup(self, exclusive=True)
        for i, modo in enumerate(MODOS.values()):
            b = QPushButton("  " + (modo.titulo_juego or modo.nombre).replace("&", "&&"), objectName="chip", checkable=True)
            pix = iconos.redondo(IMAGENES / modo.imagen, 28) if modo.imagen else None
            if pix:
                from PyQt5.QtGui import QIcon

                b.setIcon(QIcon(pix))
            b.setProperty("modo", modo.id)
            b.setChecked(modo.id == config.obtener("ultimo_modo") or i == 0)
            self.grupo.addButton(b)
            self.selector.addWidget(b)
        self.grupo.buttonClicked.connect(lambda _: self.al_mostrar())
        self.selector.addStretch()
        self.cuerpo.addLayout(self.selector)
        self.subtitulo_modo = QLabel(objectName="tenue")
        self.cuerpo.addWidget(self.subtitulo_modo)

        self.zona = QWidget()
        self.lista = QVBoxLayout(self.zona)
        self.lista.setSpacing(10)
        self.lista.setAlignment(Qt.AlignTop)
        desplazar = QScrollArea(widgetResizable=True)
        desplazar.setWidget(self.zona)
        self.cuerpo.addWidget(desplazar, 1)
        self.al_mostrar()

    def al_mostrar(self):
        while self.lista.count():
            w = self.lista.takeAt(0).widget()
            if w:
                w.setParent(None)
        boton = self.grupo.checkedButton()
        modo = MODOS[boton.property("modo")] if boton else next(iter(MODOS.values()))
        self.subtitulo_modo.setText(f"{modo.subtitulo_juego}. Haz clic en un equipo para ver cómo se juega.")
        biblioteca = P.cargar()
        equipos = cargar_equipos().get(modo.id, [])
        abierto_ya = False
        tarjetas = []
        for datos in equipos:
            t = TarjetaEquipo(datos, biblioteca, abierto=False)
            tarjetas.append(t)
        # Se abre de entrada el mejor equipo que ya puedes armar (o el primero si no tienes ninguno).
        for t in tarjetas:
            if t.completo and not abierto_ya:
                t.abierto = abierto_ya = True
                t._mostrar()
        if tarjetas and not abierto_ya:
            tarjetas[0].abierto = True
            tarjetas[0]._mostrar()
        for t in tarjetas:
            self.lista.addWidget(t)
        if not tarjetas:
            self.lista.addWidget(QLabel("Todavía no hay equipos recomendados para este contenido.", objectName="tenue"))

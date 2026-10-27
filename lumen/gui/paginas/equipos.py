"""Pagina Equipos: equipos recomendados por cada contenido, del mejor al mas dificil.

Los equipos vienen de lumen/datos/equipos.yaml (base fija que mantiene el administrador). Cada
equipo es una tarjeta desplegable: retratos (en gris los que no tienes), nivel, si el bot lo juega,
que te falta y como se juega.
"""

from pathlib import Path

import yaml
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from lumen import config
from lumen import personajes as P
from lumen.gui import iconos, tema
from lumen.gui.comun import Pagina
from lumen.gui.paginas.personajes import _en_gris
from lumen.modos import MODOS
from lumen.modos.catalogo import CATALOGO

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


def contenidos_con_equipos(equipos: dict) -> list[tuple[str, str, object, bool]]:
    """(clave, texto del boton, contenido, el bot lo juega) en el orden del catalogo. La clave es un
    destino ("perros_piso4") o un contenido entero ("perros": el resto de sus pisos)."""
    salida = []
    for c in CATALOGO:
        for clave in [c.id] + [d.id for d in c.destinos if d.id != c.id]:
            if clave not in equipos:
                continue
            destino = next((d for d in c.destinos if d.id == clave), None)
            propio = (equipos.get("_pisos") or {}).get(clave)  # "Floors 1–2" o "" (sin pisos)
            if propio is not None:
                texto = f"{c.nombre} · {propio}" if propio else c.nombre
            elif destino and destino.nombre:
                texto = f"{c.nombre} · {destino.nombre}"
            elif len(c.destinos) > 1:
                otros = [d.nombre for d in c.destinos if d.id not in equipos]
                texto = f"{c.nombre} · {otros[0]}–{otros[-1].split()[-1]}" if len(otros) > 1 else c.nombre
            else:
                texto = c.nombre
            salida.append((clave, texto, c, clave in MODOS))
    return salida


def _nombre(pid: str, biblioteca: dict, nombres: dict) -> str:
    return biblioteca[pid].nombre if pid in biblioteca else nombres.get(pid, pid)


def _retrato(pj: P.Personaje | None, nombre: str, tengo: bool, tam=(68, 68), extra: str = "",
             detalle: str = "") -> QWidget:
    caja = QWidget()
    caja.setFixedWidth(tam[0] + 40)
    if detalle:
        caja.setToolTip(detalle)
    capa = QVBoxLayout(caja)
    capa.setContentsMargins(0, 0, 0, 0)
    capa.setSpacing(2)
    foto = QLabel(alignment=Qt.AlignCenter)
    foto.setFixedSize(*tam)
    foto.setObjectName("foto_pj")
    ruta = pj.ruta_cara() if pj else None  # el icono de la lista de Heroes (o el retrato del equipo)
    if ruta and ruta.is_file():
        pix = QPixmap(str(ruta)).scaled(tam[0], tam[1], Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        pix = pix.copy((pix.width() - tam[0]) // 2, 0, tam[0], tam[1])
        foto.setPixmap(pix if tengo else _en_gris(pix))
    else:
        foto.setPixmap(iconos.pixmap("mdi6.account-question", 34, tema.TENUE))
    foto.setProperty("tengo", tengo)
    capa.addWidget(foto, 0, Qt.AlignHCenter)
    texto = QLabel(nombre, alignment=Qt.AlignHCenter | Qt.AlignTop, wordWrap=True)
    texto.setFixedWidth(tam[0] + 40)
    texto.setMinimumHeight(texto.fontMetrics().lineSpacing() * 3 + 4)  # que no se monte sobre la cara
    texto.setStyleSheet(f"color: {tema.TEXTO if tengo else tema.TENUE}; font-size: 8.5pt;")
    capa.addWidget(texto, 0, Qt.AlignHCenter)
    if extra:
        mas = QLabel(extra, alignment=Qt.AlignCenter)
        mas.setStyleSheet(f"color: {tema.ACENTO}; font-size: 8pt; font-weight: 700;")
        capa.addWidget(mas, 0, Qt.AlignHCenter)
    capa.addStretch()
    # Alto fijo: con las notas abiertas el layout encogia la tarjeta y el nombre se montaba sobre la cara.
    linea = texto.fontMetrics().lineSpacing()
    caja.setFixedHeight(tam[1] + linea * 4 + 16)
    return caja


class TarjetaEquipo(QFrame):
    """Un equipo recomendado: cabecera siempre visible y detalle desplegable."""

    def __init__(self, datos: dict, biblioteca: dict, abierto: bool, nombres: dict | None = None):
        super().__init__(objectName="tarjeta_equipo")
        capa = QVBoxLayout(self)
        capa.setContentsMargins(14, 12, 14, 12)

        nombres_extra = nombres or {}
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
        cab.addWidget(nivel, 0, Qt.AlignVCenter)
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
            nombres = [_nombre(p, biblioteca, nombres_extra) for p in faltan]
            # Con varios nombres largos la tarjeta se ensanchaba: solo cuantos (las caras en gris ya dicen cuales)
            texto = f"Te falta: {nombres[0]}" if len(nombres) == 1 else f"Te faltan {len(nombres)}"
            estado.setText(f"<span style='color:{tema.AVISO}'>{texto}</span>")
            estado.setToolTip("Te falta:\n" + "\n".join(f"• {n}" for n in nombres))
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
            nombre = _nombre(pid, biblioteca, nombres_extra)
            if pj and pj.color in P.NOMBRE_COLOR and pj.color != "sin definir":
                nombre += f" · {P.NOMBRE_COLOR[pj.color]}"  # hay varias versiones de casi todos
            extra = detalle = ""
            if pid in alternativas:
                # Debajo solo cuantas; la lista entera al pasar el raton.
                otros = []
                for a in alternativas[pid]:
                    texto = _nombre(a, biblioteca, nombres_extra)
                    if a in biblioteca and biblioteca[a].color in P.NOMBRE_COLOR:
                        texto += f" · {P.NOMBRE_COLOR[biblioteca[a].color]}"
                    otros.append(texto + (" ✓" if biblioteca.get(a) and biblioteca[a].tengo else ""))
                extra = f"+{len(otros)} opción" + ("es" if len(otros) > 1 else "")
                detalle = "También vale:\n" + "\n".join(f"• {o}" for o in otros)
            fila.addWidget(_retrato(pj, nombre, tengo, extra=extra, detalle=detalle))
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

    def resizeEvent(self, evento):
        # Las notas ocupan varias lineas: su alto depende del ancho. Sin esto, si no caben todas las
        # tarjetas, Qt encoge la abierta y el texto se monta sobre las caras.
        super().resizeEvent(evento)
        alto = self.detalle.heightForWidth(self.detalle.width()) if self.detalle.isVisible() else 0
        if alto > 0 and self.detalle.minimumHeight() != alto:
            self.detalle.setMinimumHeight(alto)


class PaginaEquipos(Pagina):
    titulo = "Equipos"
    subtitulo = "Del mejor al más difícil."

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.selector = QGridLayout()  # en filas de 3: los nombres de las bestias son largos
        self.selector.setHorizontalSpacing(8)
        self.selector.setVerticalSpacing(6)
        self.grupo = QButtonGroup(self, exclusive=True)
        self.contenidos = {}
        ultimo = config.obtener("ultimo_modo")
        for i, (clave, texto, contenido, juega) in enumerate(contenidos_con_equipos(cargar_equipos())):
            b = QPushButton("  " + texto.replace("&", "&&"), objectName="chip", checkable=True)
            foto = contenido.foto
            pix = iconos.redondo(foto, 28) if foto and foto.is_file() else None
            if pix:
                from PyQt5.QtGui import QIcon

                b.setIcon(QIcon(pix))
            else:
                b.setIcon(iconos.icono(contenido.icono, tema.TEXTO))
            b.setProperty("modo", clave)
            b.setToolTip(texto)
            b.setChecked(clave == ultimo or i == 0)
            self.contenidos[clave] = (contenido, juega)
            self.grupo.addButton(b)
            self.selector.addWidget(b, i // 3, i % 3)
        self.grupo.buttonClicked.connect(lambda _: self.al_mostrar())
        self.cuerpo.addLayout(self.selector)
        self.subtitulo_modo = QLabel(objectName="tenue")
        self.cuerpo.addWidget(self.subtitulo_modo)

        self.zona = QWidget()
        self.lista = QVBoxLayout(self.zona)
        self.lista.setSpacing(10)
        desplazar = QScrollArea(widgetResizable=True)
        desplazar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        desplazar.setWidget(self.zona)
        self.cuerpo.addWidget(desplazar, 1)
        self.al_mostrar()

    def al_mostrar(self):
        while self.lista.count():
            w = self.lista.takeAt(0).widget()
            if w:
                w.setParent(None)
        boton = self.grupo.checkedButton()
        clave = boton.property("modo") if boton else ""
        contenido, juega = self.contenidos.get(clave, (None, False))
        if contenido:
            estado = "El bot ya lo farmea" if juega else "El bot todavía no lo farmea"
            self.subtitulo_modo.setText(f"{contenido.descripcion} · {estado}. Haz clic en un equipo para ver cómo se juega.")
        biblioteca = P.cargar()
        todos = cargar_equipos()
        equipos = todos.get(clave, [])
        abierto_ya = False
        tarjetas = []
        for datos in equipos:
            t = TarjetaEquipo(datos, biblioteca, abierto=False, nombres=todos.get("_nombres") or {})
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
        # Relleno al final en vez de alinear arriba: con AlignTop Qt calculaba mal el alto de las notas
        # (texto en varias lineas) y montaba el texto sobre las caras.
        self.lista.addStretch(1)

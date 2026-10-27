"""Pagina Heroes capturados (solo administrador): revisar lo que guardo la captura en serie.

Muestra cada heroe de capturas/heroes/catalogo.yaml con su cara, datos y cartas, marca lo que conviene
revisar y deja corregirlo o quitarlo antes de publicarlo en la base del bot.
"""

import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from trefot import personajes as P
from trefot.gui import iconos, tema
from trefot.gui.comun import Pagina, tarjeta
from trefot.modos import captura_heroes as C
from trefot.vision import guardar_imagen, leer_imagen

COLOR_ATRIBUTO = {"rojo": "#e05a4f", "verde": "#4cc38a", "azul": "#4f8fe0", "claro": "#e6c84c", "oscuro": "#a06ad8"}
ATRIBUTOS = ["Strength", "Speed", "HP", "Light", "Dark"]
RAZAS = ["Human", "Giant", "Fairy", "Goddess", "Demon", "Unknown"]
TIPOS = {"single": "Un objetivo", "area": "Área", "defensa": "Defensa", "apoyo": "Apoyo", "otro": "Otro"}
COLOR_TIPO = {"single": "#4f8fe0", "area": "#e05a4f", "defensa": "#a06ad8", "apoyo": "#4cc38a", "otro": "#8b90a3"}


def avisos_de(h: dict) -> list[str]:
    """Lo que conviene revisar en un heroe capturado."""
    avisos = []
    if len(h.get("cartas") or []) < 3:
        avisos.append(f"solo {len(h.get('cartas') or [])} cartas")
    if not h.get("titulo"):
        avisos.append("sin título")
    if h.get("raza", "sin definir") == "sin definir":
        avisos.append("sin raza")
    if h.get("color", "sin definir") == "sin definir":
        avisos.append("sin atributo")
    if any(c.get("tipo") == "otro" for c in h.get("cartas") or []):
        avisos.append("carta de tipo dudoso")
    return avisos


def retrato(pid: str) -> QPixmap:
    """Cara del heroe: el icono de la lista de Heroes si se capturo; si no, el de su habilidad Unique
    (las capturas de antes del retrato lo sacan ahora de su ficha.jpg)."""
    icono = C.CARPETA / pid / "icono.png"
    if icono.is_file():
        return QPixmap(str(icono))
    ruta = C.CARPETA / pid / "retrato_ficha.png"
    if not ruta.is_file():
        ficha = leer_imagen(C.CARPETA / pid / "ficha.jpg")
        if ficha is not None:
            try:
                guardar_imagen(ruta, C.recorte_retrato(ficha))
            except Exception:
                pass
    return QPixmap(str(ruta))


def _chip(texto: str, color: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setStyleSheet(f"background: {color}; color: {tema.FONDO}; border-radius: 8px; padding: 1px 8px; "
                           "font-weight: 700; font-size: 8.5pt;")
    return etiqueta


class DialogoHeroe(QDialog):
    """Corregir a mano lo que el lector de texto leyo mal."""

    def __init__(self, padre, h: dict):
        super().__init__(padre)
        self.setWindowTitle(f"Corregir · {h.get('nombre', '')}")
        self.setMinimumWidth(560)
        self.h = h
        capa = QVBoxLayout(self)
        form = QFormLayout()
        self.nombre = QLineEdit(h.get("nombre", ""))
        self.titulo = QLineEdit(h.get("titulo", ""))
        self.atributo = QComboBox()
        self.atributo.addItems(ATRIBUTOS)
        self.atributo.setCurrentText(h.get("atributo", ""))
        self.raza = QComboBox()
        self.raza.addItems(RAZAS)
        self.raza.setCurrentText(h.get("raza_juego", ""))
        self.caracteristicas = QLineEdit(h.get("caracteristicas", ""))
        form.addRow("Nombre", self.nombre)
        form.addRow("Título", self.titulo)
        form.addRow("Attribute", self.atributo)
        form.addRow("Race", self.raza)
        form.addRow("Characteristics", self.caracteristicas)
        capa.addLayout(form)
        self.cartas = []
        for i, c in enumerate(h.get("cartas") or [], start=1):
            fila = QHBoxLayout()
            nombre = QLineEdit(c.get("nombre", ""))
            tipo = QComboBox()
            for clave, texto in TIPOS.items():
                tipo.addItem(texto, clave)
            tipo.setCurrentIndex(max(0, tipo.findData(c.get("tipo"))))
            ulti = QCheckBox("Ultimate", checked=bool(c.get("ulti")))
            fila.addWidget(QLabel(f"Carta {i}"))
            fila.addWidget(nombre, 1)
            fila.addWidget(tipo)
            fila.addWidget(ulti)
            capa.addLayout(fila)
            self.cartas.append((nombre, tipo, ulti))
        botones = QHBoxLayout()
        botones.addStretch()
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        guardar = QPushButton("Guardar", objectName="primario")
        guardar.clicked.connect(self._guardar)
        botones.addWidget(cancelar)
        botones.addWidget(guardar)
        capa.addLayout(botones)

    def _guardar(self):
        h = self.h
        h["nombre"] = self.nombre.text().strip()
        h["titulo"] = self.titulo.text().strip()
        h["clave"] = f"[{h['titulo']}] {h['nombre']}" if h["titulo"] else h["nombre"]
        h["atributo"] = self.atributo.currentText()
        h["color"] = C.COLOR.get(h["atributo"].lower(), "sin definir")
        h["raza_juego"] = self.raza.currentText()
        h["raza"] = C.RAZA_ES.get(h["raza_juego"].lower(), "sin definir")
        h["caracteristicas"] = self.caracteristicas.text().strip()
        for c, (nombre, tipo, ulti) in zip(h.get("cartas") or [], self.cartas):
            c["nombre"] = nombre.text().strip()
            c["tipo"] = tipo.currentData()
            c["ulti"] = ulti.isChecked()
        h["revisado"] = True
        self.accept()


class FilaHeroe(QFrame):
    def __init__(self, pagina, pid: str, h: dict):
        super().__init__(objectName="tarjeta_equipo")
        fila = QHBoxLayout(self)
        fila.setContentsMargins(12, 10, 12, 10)
        fila.setSpacing(14)

        cara = QLabel(alignment=Qt.AlignCenter)
        cara.setFixedSize(78, 78)
        pix = retrato(pid)
        if not pix.isNull():
            cara.setPixmap(pix.scaled(78, 78, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        fila.addWidget(cara, 0, Qt.AlignTop)

        datos = QVBoxLayout()
        datos.setSpacing(3)
        datos.addWidget(QLabel(h.get("nombre") or "(sin nombre)", objectName="titulo_seccion"))
        datos.addWidget(QLabel(f"[{h['titulo']}]" if h.get("titulo") else "sin título", objectName="tenue"))
        chips = QHBoxLayout()
        chips.setSpacing(6)
        chips.addWidget(_chip(h.get("atributo") or "?", COLOR_ATRIBUTO.get(h.get("color"), tema.TENUE)))
        chips.addWidget(QLabel(h.get("raza_juego") or "raza ?", objectName="tenue"))
        if h.get("caracteristicas"):
            chips.addWidget(QLabel(f"· {h['caracteristicas']}", objectName="tenue"))
        chips.addStretch()
        datos.addLayout(chips)
        avisos = avisos_de(h)
        if avisos:
            datos.addWidget(QLabel(f"<span style='color:{tema.AVISO}'>Revisar: {', '.join(avisos)}</span>"))
        elif h.get("revisado"):
            datos.addWidget(QLabel(f"<span style='color:{tema.OK}'>Revisado</span>"))
        datos.addStretch()
        fila.addLayout(datos, 2)

        cartas = QHBoxLayout()
        cartas.setSpacing(8)
        for i, c in enumerate(h.get("cartas") or [], start=1):
            caja = QVBoxLayout()
            caja.setSpacing(2)
            imagen = QLabel(alignment=Qt.AlignCenter)
            carta_pix = QPixmap(str(C.CARPETA / pid / f"carta_{i}{P.SUFIJO_FICHA}.png"))
            if not carta_pix.isNull():
                imagen.setPixmap(carta_pix.scaledToHeight(70, Qt.SmoothTransformation))
            imagen.setToolTip(c.get("texto", ""))
            caja.addWidget(imagen)
            nombre = QLabel(c.get("nombre", ""), alignment=Qt.AlignCenter, wordWrap=True)
            nombre.setFixedWidth(104)
            nombre.setToolTip(c.get("texto", ""))
            caja.addWidget(nombre)
            tipo = "ulti" if c.get("ulti") else c.get("tipo", "otro")
            chip = _chip("Ultimate" if c.get("ulti") else TIPOS.get(tipo, tipo),
                         tema.ACENTO if c.get("ulti") else COLOR_TIPO.get(tipo, tema.TENUE))
            caja.addWidget(chip, 0, Qt.AlignHCenter)
            cartas.addLayout(caja)
        cartas.addStretch()
        fila.addLayout(cartas, 3)

        botones = QVBoxLayout()
        b_editar = QPushButton(" Corregir", objectName="chico")
        b_editar.setIcon(iconos.icono("mdi6.pencil", tema.TEXTO))
        b_editar.clicked.connect(lambda: pagina.editar(pid))
        b_quitar = QPushButton(" Quitar", objectName="chico")
        b_quitar.setIcon(iconos.icono("mdi6.delete-outline", tema.TEXTO))
        b_quitar.clicked.connect(lambda: pagina.quitar(pid))
        botones.addWidget(b_editar)
        botones.addWidget(b_quitar)
        botones.addStretch()
        fila.addLayout(botones)


class PaginaHeroesCapturados(Pagina):
    titulo = "Héroes capturados"
    subtitulo = ("Lo que guardó la captura (se guarda sola mientras captura). Revísalo y pulsa \"Pasar a Personajes\". "
                 "Pasa el ratón por una carta para leer su descripción.")

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.catalogo: dict = {}
        for texto, ic, funcion, primario in (
            ("Pasar a Personajes", "personajes", self._pasar, True),
            ("Capturar todos los héroes", "jugar", self._capturar, False),
            ("Abrir carpeta", "carpeta", self._abrir_carpeta, False),
            ("Recargar", "actualizar", self.al_mostrar, False),
        ):
            b = QPushButton(" " + texto, objectName="primario" if primario else "chico")
            b.setIcon(iconos.icono(ic, tema.SOBRE_ACENTO if primario else tema.TEXTO))
            b.clicked.connect(funcion)
            self.acciones.addWidget(b)

        fila = QHBoxLayout()
        self.cifras = {}
        for clave, titulo, ic in (("heroes", "Héroes capturados", "personajes"), ("cartas", "Cartas", "cartas"),
                                  ("revisar", "Para revisar", "falta")):
            marco, cifra = tarjeta(titulo, icono=ic)
            self.cifras[clave] = cifra
            fila.addWidget(marco)
        self.cuerpo.addLayout(fila)

        barra = QHBoxLayout()
        self.buscar = QLineEdit(placeholderText="Buscar héroe...")
        self.buscar.setClearButtonEnabled(True)
        self.buscar.setMaximumWidth(280)
        self.buscar.textChanged.connect(self._pintar)
        barra.addWidget(self.buscar)
        self.filtro = QButtonGroup(self, exclusive=True)
        for i, texto in enumerate(("Todos", "Para revisar")):
            b = QPushButton(texto, objectName="chip", checkable=True)
            b.setChecked(i == 0)
            self.filtro.addButton(b, i)
            barra.addWidget(b)
        self.filtro.buttonClicked.connect(lambda _: self._pintar())
        barra.addStretch()
        self.cuerpo.addLayout(barra)

        self.lista = QVBoxLayout()
        self.lista.setSpacing(8)
        contenido = QWidget()
        contenido.setLayout(self.lista)
        zona = QScrollArea(widgetResizable=True)
        zona.setWidget(contenido)
        self.cuerpo.addWidget(zona, 1)

    def al_mostrar(self):
        self.catalogo = C.cargar_catalogo()
        if C.reclasificar(self.catalogo):  # capturas de antes de mejorar la clasificacion de cartas
            C.guardar_catalogo(self.catalogo)
        self._pintar()

    def _pintar(self):
        while self.lista.count():
            item = self.lista.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        heroes = sorted(self.catalogo.items(), key=lambda kv: (kv[1].get("nombre") or "").lower())
        para_revisar = [pid for pid, h in heroes if avisos_de(h)]
        self.cifras["heroes"].setText(str(len(heroes)))
        self.cifras["cartas"].setText(str(sum(len(h.get("cartas") or []) for _, h in heroes)))
        self.cifras["revisar"].setText(str(len(para_revisar)))
        texto = self.buscar.text().strip().lower()
        solo_revisar = self.filtro.checkedId() == 1
        visibles = [(pid, h) for pid, h in heroes
                    if (not texto or texto in (h.get("clave") or "").lower()) and (not solo_revisar or pid in para_revisar)]
        for pid, h in visibles:
            self.lista.addWidget(FilaHeroe(self, pid, h))
        if not heroes:
            self.lista.addWidget(QLabel("Todavía no hay héroes capturados. En el juego abre la ficha del primer héroe "
                                        "y pulsa \"Capturar todos los héroes\".", objectName="tenue", wordWrap=True))
        elif not visibles:
            self.lista.addWidget(QLabel("Ningún héroe coincide.", objectName="tenue"))
        self.lista.addStretch()

    def editar(self, pid: str):
        if DialogoHeroe(self, self.catalogo[pid]).exec_():
            C.guardar_catalogo(self.catalogo)
            self._pintar()

    def quitar(self, pid: str):
        nombre = self.catalogo[pid].get("nombre", pid)
        r = QMessageBox.question(self, "Quitar", f"¿Quitar a {nombre} de los capturados? Sus imágenes se quedan "
                                 "en la carpeta; puedes volver a capturarlo.")
        if r == QMessageBox.Yes:
            del self.catalogo[pid]
            C.guardar_catalogo(self.catalogo)
            self._pintar()

    def _pasar(self):
        if not self.catalogo:
            QMessageBox.information(self, "Pasar a Personajes", "Todavía no hay héroes capturados.")
            return
        revisar = sum(1 for h in self.catalogo.values() if avisos_de(h))
        r = QMessageBox.question(
            self, "Pasar a Personajes",
            f"Paso {len(self.catalogo)} héroes a la página Personajes y los marco como tuyos."
            + (f"\n\n{revisar} tienen algo para revisar; puedes corregirlos después y volver a pasarlos." if revisar else "")
            + "\n\nLos que el bot ya conocía (Odin, Gawain, Freyja, Thonar...) solo reciben su icono: sus cartas no "
              "se tocan. ¿Seguir?")
        if r != QMessageBox.Yes:
            return
        try:
            nuevos, existentes = C.pasar_a_biblioteca(self.catalogo)
        except Exception as error:
            QMessageBox.warning(self, "Pasar a Personajes", f"No pude pasarlos: {error}")
            return
        self.app.paginas["personajes"].al_mostrar()
        QMessageBox.information(
            self, "Pasar a Personajes",
            f"Listo: {nuevos} héroes nuevos y {existentes} que ya estaban, ahora en Personajes y marcados como tuyos.\n\n"
            "Por ahora solo los ves tú. Para que les lleguen a todos con la próxima actualización, avísame y los "
            "publico en la base del bot.")
        self.app.navegar("personajes")

    def _capturar(self):
        self.app.paginas["editor"].captura_en_serie()

    def _abrir_carpeta(self):
        C.CARPETA.mkdir(parents=True, exist_ok=True)
        os.startfile(C.CARPETA)

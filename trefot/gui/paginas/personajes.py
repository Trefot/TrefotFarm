"""Pagina Personajes: la biblioteca. Ficha de cada personaje con sus cartas, retrato, roles y si lo tienes."""

import os
from pathlib import Path

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QColor, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from trefot import personajes as P
from trefot import juego, ventana
from trefot.equipo import recorte_desde_ficha, recorte_retrato
from trefot.gui import tema
from trefot.gui.comun import Pagina, a_pixmap
from trefot.modos import MODOS
from trefot.rutas import CAPTURAS, IMAGENES
from trefot.vision import guardar_imagen, leer_imagen

COLOR_ATRIBUTO = {"rojo": "#e05a4f", "verde": "#4cc38a", "azul": "#4f8fe0", "claro": "#e6c84c", "oscuro": "#a06ad8"}


def modos_que_usan(pid: str) -> list[str]:
    return [m.nombre for m in MODOS.values() if getattr(m, "equipo", None) and pid in m.equipo.orden]


class DialogoRetratos(QDialog):
    """Recorta las 4 caras de la pantalla del equipo y deja elegir de quien es cada una."""

    def __init__(self, padre, pantalla, biblioteca: dict[str, P.Personaje], sugeridos: list[str]):
        super().__init__(padre)
        self.setWindowTitle("Retratos del equipo")
        self.pantalla = pantalla
        capa = QVBoxLayout(self)
        capa.addWidget(QLabel("Elige quien esta en cada puesto (izquierda a derecha) y pulsa Guardar.", objectName="tenue"))
        fila = QHBoxLayout()
        self.combos = []
        for puesto in range(4):
            caja = QFrame(objectName="tarjeta")
            c = QVBoxLayout(caja)
            img = QLabel(alignment=Qt.AlignCenter)
            img.setPixmap(a_pixmap(recorte_retrato(pantalla, puesto), 96))
            c.addWidget(img)
            combo = QComboBox()
            combo.addItem("(no guardar)", None)
            for pj in biblioteca.values():
                combo.addItem(pj.nombre, pj.id)
            if puesto < len(sugeridos):
                combo.setCurrentIndex(max(0, combo.findData(sugeridos[puesto])))
            c.addWidget(combo)
            self.combos.append(combo)
            fila.addWidget(caja)
        capa.addLayout(fila)
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
        for puesto, combo in enumerate(self.combos):
            pid = combo.currentData()
            if pid:
                guardar_imagen(P.CARPETA / pid / f"{P.RETRATO}.png", recorte_retrato(self.pantalla, puesto))
        self.accept()


class DialogoFicha(QDialog):
    """Saca las 3 cartas de la fila Skills de la ficha del heroe y las guarda en la biblioteca."""

    def __init__(self, padre, pantalla, biblioteca: dict[str, P.Personaje], sugerido: str | None):
        super().__init__(padre)
        self.setWindowTitle("Cartas desde la ficha del heroe")
        self.pantalla, self.biblioteca, self.guardado = pantalla, biblioteca, None
        capa = QVBoxLayout(self)
        capa.addWidget(QLabel(
            "En el juego: Heroes -> el personaje (su ficha, con la fila 'Skills' abajo). "
            "Elige de quien es y que carta es cada una.", objectName="tenue", wordWrap=True))
        fila_pj = QHBoxLayout()
        fila_pj.addWidget(QLabel("Personaje:"))
        self.combo_pj = QComboBox()
        for pj in biblioteca.values():
            self.combo_pj.addItem(pj.nombre, pj.id)
        self.combo_pj.setCurrentIndex(max(0, self.combo_pj.findData(sugerido)))
        fila_pj.addWidget(self.combo_pj, 1)
        self.color = QComboBox()
        self.color.addItems(P.COLORES)
        self.raza = QComboBox()
        self.raza.addItems(P.RAZAS)
        fila_pj.addWidget(QLabel("Color:"))
        fila_pj.addWidget(self.color)
        fila_pj.addWidget(QLabel("Raza:"))
        fila_pj.addWidget(self.raza)
        capa.addLayout(fila_pj)
        capa.addWidget(QLabel("Color y raza: copialos de 'Attribute' y 'Race' de la ficha.", objectName="tenue"))

        fila = QHBoxLayout()
        self.combos = []
        for i, (x1, y1, x2, y2) in enumerate(juego.FICHA_CARTAS):
            caja = QFrame(objectName="tarjeta")
            c = QVBoxLayout(caja)
            img = QLabel(alignment=Qt.AlignCenter)
            img.setPixmap(a_pixmap(pantalla[y1:y2, x1:x2], 90))
            c.addWidget(img)
            combo = QComboBox()
            c.addWidget(combo)
            self.combos.append(combo)
            fila.addWidget(caja)
        capa.addLayout(fila)
        self.combo_pj.currentIndexChanged.connect(self._cambiar_pj)
        self._cambiar_pj()

        botones = QHBoxLayout()
        botones.addStretch()
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        guardar = QPushButton("Guardar", objectName="primario")
        guardar.clicked.connect(self._guardar)
        botones.addWidget(cancelar)
        botones.addWidget(guardar)
        capa.addLayout(botones)

    def _cambiar_pj(self):
        pj = self.biblioteca[self.combo_pj.currentData()]
        self.color.setCurrentText(pj.color)
        self.raza.setCurrentText(pj.raza)
        cartas = [c for c in pj.cartas.values() if not c.boton]
        for i, combo in enumerate(self.combos):
            combo.clear()
            combo.addItem("(no guardar)", None)
            for c in cartas:
                combo.addItem(c.descripcion, c.id)
            if i < len(cartas):  # por defecto: normal 1, normal 2, ulti en el orden de la ficha
                combo.setCurrentIndex(i + 1)

    def _guardar(self):
        pj = self.biblioteca[self.combo_pj.currentData()]
        for i, combo in enumerate(self.combos):
            if combo.currentData():
                guardar_imagen(pj.ruta_ficha(combo.currentData()), recorte_desde_ficha(self.pantalla, i))
        pj.color, pj.raza = self.color.currentText(), self.raza.currentText()
        P.guardar(pj)
        self.guardado = pj.id
        self.accept()


class TarjetaCartaPj(QFrame):
    """Una carta de la ficha: su imagen (propia, de AutoFarming o ninguna) y la opcion de borrarla."""

    def __init__(self, pagina, pj: P.Personaje, carta: P.CartaPj | None, titulo: str, clave: str):
        super().__init__(objectName="tarjeta")
        self.setFixedWidth(150)
        self.setMinimumHeight(220)  # con o sin boton "Borrar", que nada se monte
        capa = QVBoxLayout(self)
        capa.setContentsMargins(8, 8, 8, 8)
        imagen = QLabel(alignment=Qt.AlignCenter)
        imagen.setFixedHeight(96)
        estado = pj.estado_carta(clave) if carta else ("propia" if pj.tiene_captura(clave) else "falta")
        ruta = {"propia": pj.ruta(clave), "ficha": pj.ruta_ficha(clave),
                "respaldo": IMAGENES / carta.respaldo if carta else None}.get(estado)
        if ruta:
            imagen.setPixmap(QPixmap(str(ruta)).scaled(120, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            imagen.setText("sin captura")
        capa.addWidget(imagen)
        capa.addWidget(QLabel(f"<b>{titulo}</b>", wordWrap=True))
        texto, color = {"propia": ("✔ de una pelea", tema.OK), "ficha": ("✔ de la ficha", tema.OK),
                        "respaldo": ("◐ de AutoFarming", tema.AVISO),
                        "falta": ("✖ falta", tema.ERROR)}[estado]
        capa.addWidget(QLabel(f"<span style='color:{color}'>{texto}</span>"))
        if estado in ("propia", "ficha"):
            b = QPushButton("Borrar captura")
            b.setStyleSheet("padding: 4px;")
            b.clicked.connect(lambda: pagina.borrar_captura(pj, clave))
            capa.addWidget(b)
        capa.addStretch()


class PaginaPersonajes(Pagina):
    titulo = "Personajes"
    subtitulo = "Abre la ficha del heroe en el juego y pulsa 'Desde la ficha'. Sirve para todos los modos."

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.biblioteca: dict[str, P.Personaje] = {}
        self.actual: P.Personaje | None = None

        for texto, funcion, primario in (
            ("Desde la ficha", self.ficha_desde_juego, True),
            ("Ficha (foto)...", self.ficha_desde_foto, False),
            ("Retratos", self.retratos_desde_juego, False),
            ("Retratos (foto)...", self.retratos_desde_foto, False),
            ("Nuevo", self.nuevo, False),
            ("Carpeta", lambda: os.startfile(P.CARPETA), False),
        ):
            b = QPushButton(texto, objectName="primario" if primario else "")
            b.clicked.connect(funcion)
            self.acciones.addWidget(b)

        fila = QHBoxLayout()
        # ---- lista
        izq = QVBoxLayout()
        self.buscar = QLineEdit(placeholderText="Buscar...")
        self.buscar.textChanged.connect(self._pintar_lista)
        self.solo_mios = QCheckBox("Solo los que tengo")
        self.solo_mios.toggled.connect(self._pintar_lista)
        self.lista = QListWidget()
        self.lista.setIconSize(QSize(40, 40))
        self.lista.currentItemChanged.connect(lambda item, _: self._mostrar(item.data(Qt.UserRole) if item else None))
        self.resumen = QLabel(objectName="tenue")
        for w in (self.buscar, self.solo_mios, self.lista, self.resumen):
            izq.addWidget(w)
        contenedor_izq = QWidget()
        contenedor_izq.setLayout(izq)
        contenedor_izq.setFixedWidth(270)
        fila.addWidget(contenedor_izq)

        # ---- ficha
        self.ficha = QWidget()
        capa = QVBoxLayout(self.ficha)
        capa.setContentsMargins(0, 0, 6, 0)
        datos = QGroupBox("Datos")
        f = QFormLayout(datos)
        self.nombre = QLineEdit()
        self.color = QComboBox()
        self.color.addItems(P.COLORES)
        self.raza = QComboBox()
        self.raza.addItems(P.RAZAS)
        self.tengo = QCheckBox("Lo tengo")
        self.usado = QLabel(objectName="tenue", wordWrap=True)
        f.addRow("Nombre", self.nombre)
        f.addRow("Color", self.color)
        f.addRow("Raza", self.raza)
        f.addRow("", self.tengo)
        f.addRow("Se usa en", self.usado)
        capa.addWidget(datos)

        roles = QGroupBox("Que hace en un equipo (roles)")
        rejilla = QGridLayout(roles)
        self.roles: dict[str, QCheckBox] = {}
        for i, (clave, texto) in enumerate(P.ROLES.items()):
            chk = QCheckBox(texto)
            self.roles[clave] = chk
            rejilla.addWidget(chk, i // 3, i % 3)
        capa.addWidget(roles)

        cartas = QGroupBox("Cartas y retrato")
        capa_cartas = QVBoxLayout(cartas)
        self.zona_cartas = QHBoxLayout()
        self.zona_cartas.setAlignment(Qt.AlignLeft)
        capa_cartas.addLayout(self.zona_cartas)
        capa.addWidget(cartas)

        botones = QHBoxLayout()
        self.b_guardar = QPushButton("Guardar cambios", objectName="primario")
        self.b_guardar.clicked.connect(self.guardar)
        self.b_borrar = QPushButton("Quitar de la biblioteca")
        self.b_borrar.clicked.connect(self.borrar)
        b_carta = QPushButton("Agregar carta")
        b_carta.clicked.connect(self.agregar_carta)
        botones.addWidget(self.b_guardar)
        botones.addWidget(b_carta)
        botones.addWidget(self.b_borrar)
        botones.addStretch()
        capa.addLayout(botones)
        capa.addStretch()

        desplazar = QScrollArea(widgetResizable=True)
        desplazar.setWidget(self.ficha)
        fila.addWidget(desplazar, 1)
        self.cuerpo.addLayout(fila, 1)
        self.al_mostrar()

    # ------------------------------------------------------------------- lista
    def al_mostrar(self):
        seleccion = self.actual.id if self.actual else None
        self.biblioteca = P.cargar()
        self._pintar_lista(seleccion=seleccion)

    def _pintar_lista(self, *_args, seleccion: str | None = None):
        seleccion = seleccion or (self.actual.id if self.actual else None)
        texto = self.buscar.text().strip().lower()
        self.lista.blockSignals(True)
        self.lista.clear()
        fila_sel = 0
        for pj in sorted(self.biblioteca.values(), key=lambda x: (not x.tengo, x.nombre.lower())):
            if texto and texto not in pj.nombre.lower():
                continue
            if self.solo_mios.isChecked() and not pj.tengo:
                continue
            cartas = [c for c in pj.cartas.values()]
            listas = sum(1 for c in cartas if pj.estado_carta(c.id) != "falta")
            item = QListWidgetItem(f"{pj.nombre}\n{pj.color} · {listas}/{len(cartas)} cartas" + ("" if pj.tengo else " · no lo tengo"))
            if pj.tiene_captura(P.RETRATO):
                item.setIcon(QIcon(QPixmap(str(pj.ruta(P.RETRATO)))))
            item.setForeground(QColor(tema.TEXTO if pj.tengo else tema.TENUE))
            item.setData(Qt.UserRole, pj.id)
            self.lista.addItem(item)
            if pj.id == seleccion:
                fila_sel = self.lista.count() - 1
        self.lista.blockSignals(False)
        tengo = sum(1 for p in self.biblioteca.values() if p.tengo)
        self.resumen.setText(f"{len(self.biblioteca)} personajes · tienes {tengo}")
        if self.lista.count():
            self.lista.setCurrentRow(fila_sel)
            self._mostrar(self.lista.currentItem().data(Qt.UserRole))
        else:
            self._mostrar(None)

    # ------------------------------------------------------------------- ficha
    def _mostrar(self, pid: str | None):
        self.actual = self.biblioteca.get(pid) if pid else None
        self.ficha.setEnabled(self.actual is not None)
        while self.zona_cartas.count():
            w = self.zona_cartas.takeAt(0).widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        if not self.actual:
            return
        pj = self.actual
        self.nombre.setText(pj.nombre)
        self.color.setCurrentText(pj.color)
        self.raza.setCurrentText(pj.raza)
        self.tengo.setChecked(pj.tengo)
        usado = modos_que_usan(pj.id)
        self.usado.setText(", ".join(usado) if usado else "ningun modo todavia")
        for clave, chk in self.roles.items():
            chk.setChecked(clave in pj.roles)
        for c in pj.cartas.values():
            self.zona_cartas.addWidget(TarjetaCartaPj(self, pj, c, c.descripcion + (" (boton)" if c.boton else ""), c.id))
        self.zona_cartas.addWidget(TarjetaCartaPj(self, pj, None, "Retrato", P.RETRATO))
        self.b_borrar.setVisible(pj.propio)

    def guardar(self):
        pj = self.actual
        if not pj:
            return
        pj.nombre = self.nombre.text().strip() or pj.nombre
        pj.color = self.color.currentText()
        pj.raza = self.raza.currentText()
        pj.tengo = self.tengo.isChecked()
        pj.roles = [clave for clave, chk in self.roles.items() if chk.isChecked()]
        P.guardar(pj)
        self._cambio()
        QMessageBox.information(self, "Personajes", f"Guardado {pj.nombre}.")

    def nuevo(self):
        nombre, ok = QInputDialog.getText(self, "Nuevo personaje", "Nombre (p. ej. 'Meliodas azul'):")
        if not ok or not nombre.strip():
            return
        pid = P.nuevo_id(nombre, self.biblioteca)
        pj = P.Personaje(id=pid, nombre=nombre.strip(), tengo=True, propio=True, cartas={
            "single": P.CartaPj("single", "Un objetivo"),
            "area": P.CartaPj("area", "Area"),
            "ulti": P.CartaPj("ulti", "Ulti"),
        })
        P.guardar(pj)
        self.biblioteca = P.cargar()
        self._pintar_lista(seleccion=pid)

    def agregar_carta(self):
        pj = self.actual
        if not pj:
            return
        nombre, ok = QInputDialog.getText(self, "Agregar carta", "Nombre de la carta (p. ej. 'Postura'):")
        if not ok or not nombre.strip():
            return
        cid = P.nuevo_id(nombre, pj.cartas)
        pj.cartas[cid] = P.CartaPj(cid, nombre.strip())
        P.guardar(pj)
        self._cambio()

    def borrar(self):
        pj = self.actual
        if not pj or not pj.propio:
            return
        r = QMessageBox.question(self, "Quitar", f"¿Quitar a {pj.nombre} de la biblioteca? Sus capturas quedan en la carpeta.")
        if r == QMessageBox.Yes:
            P.borrar_propio(pj.id)
            self.actual = None
            self.al_mostrar()
            self.app.refrescar_insignias()

    def borrar_captura(self, pj: P.Personaje, clave: str):
        r = QMessageBox.question(self, "Borrar captura", f"¿Borrar la captura '{clave}' de {pj.nombre}?")
        if r == QMessageBox.Yes:
            pj.ruta(clave).unlink(missing_ok=True)
            pj.ruta_ficha(clave).unlink(missing_ok=True)
            self._cambio()

    def _cambio(self):
        """Tras cualquier cambio: recargar la biblioteca y los equipos de los modos."""
        for modo in MODOS.values():
            if getattr(modo, "equipo", None):
                modo.equipo.recargar()
        self.al_mostrar()
        self.app.refrescar_insignias()

    # ----------------------------------------------------------------- retratos
    def _sugeridos(self) -> list[str]:
        from trefot import config

        modo = MODOS.get(config.obtener("ultimo_modo"))
        return modo.equipo.orden if modo and getattr(modo, "equipo", None) else []

    def _dialogo_retratos(self, pantalla):
        if DialogoRetratos(self, pantalla, self.biblioteca, self._sugeridos()).exec_():
            self._cambio()

    def retratos_desde_juego(self):
        try:
            pantalla, _ = ventana.capturar()
        except Exception as error:
            QMessageBox.warning(self, "Retratos", str(error))
            return
        self._dialogo_retratos(pantalla)

    def _dialogo_ficha(self, pantalla):
        sugerido = self.actual.id if self.actual else None
        dialogo = DialogoFicha(self, pantalla, self.biblioteca, sugerido)
        if dialogo.exec_():
            self._cambio()
            self._pintar_lista(seleccion=dialogo.guardado)

    def ficha_desde_juego(self):
        try:
            pantalla, _ = ventana.capturar()
        except Exception as error:
            QMessageBox.warning(self, "Ficha del heroe", str(error))
            return
        self._dialogo_ficha(pantalla)

    def ficha_desde_foto(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Foto de la ficha de un heroe", str(CAPTURAS), "Imagenes (*.png *.jpg)")
        if ruta:
            pantalla = leer_imagen(Path(ruta))
            if pantalla is not None:
                self._dialogo_ficha(pantalla)

    def retratos_desde_foto(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Foto de la pantalla del equipo", str(CAPTURAS), "Imagenes (*.png *.jpg)")
        if ruta:
            pantalla = leer_imagen(Path(ruta))
            if pantalla is not None:
                self._dialogo_retratos(pantalla)

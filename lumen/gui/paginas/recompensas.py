"""Pagina Recompensas: sumatoria de lo conseguido farmeando (y las fotos de cada victoria)."""

import os
import time

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from lumen import botin, recompensas
from lumen.gui import iconos, tema
from lumen.gui.comun import Pagina, tarjeta

MAXIMO_EN_GALERIA = 400
ANCHO_MINIATURA = 110
COLUMNAS_BOTIN = 5


def _miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


class CasillaObjeto(QFrame):
    """Un objeto del botin: su dibujo, cuanto llevas, el nombre y cada cuanto sale."""

    renombrar = pyqtSignal(str)

    def __init__(self, oid: str, nombre: str, total: int, por_victoria: str, veces: str, sin_nombre: bool):
        super().__init__(objectName="tarjeta_objeto")
        self.oid = oid
        self.setProperty("sin_nombre", sin_nombre)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Doble clic para ponerle nombre")
        self.setFixedHeight(190)
        capa = QVBoxLayout(self)
        capa.setContentsMargins(10, 12, 10, 10)
        capa.setSpacing(4)
        foto = QLabel(objectName="foto_objeto", alignment=Qt.AlignCenter)
        foto.setFixedSize(76, 64)
        pix = QPixmap(str(botin.ruta_icono(oid)))
        if not pix.isNull():
            foto.setPixmap(pix.scaled(68, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        capa.addWidget(foto, 0, Qt.AlignHCenter)
        capa.addWidget(QLabel(f"×{_miles(total)}", objectName="cantidad_objeto", alignment=Qt.AlignCenter))
        etiqueta = QLabel(nombre, alignment=Qt.AlignCenter, wordWrap=True)
        etiqueta.setStyleSheet(f"color: {tema.AVISO if sin_nombre else tema.TEXTO}; font-weight: 600;")
        capa.addWidget(etiqueta)
        capa.addWidget(QLabel(f"{por_victoria} por victoria", objectName="tenue", alignment=Qt.AlignCenter))
        capa.addWidget(QLabel(veces, objectName="tenue", alignment=Qt.AlignCenter))

    def mouseDoubleClickEvent(self, evento):
        self.renombrar.emit(self.oid)
        super().mouseDoubleClickEvent(evento)


class PaginaRecompensas(Pagina):
    titulo = "Recompensas"
    subtitulo = "Todo lo que has conseguido farmeando. Doble clic en un objeto para ponerle nombre."

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.registros: list[dict] = []
        self.seleccion: dict | None = None
        self._miniaturas: dict[str, QIcon] = {}

        for texto, ic, funcion in (("Volver a analizar", "buscar", self._reanalizar),
                                   ("Abrir carpeta", "carpeta", self._abrir_carpeta),
                                   ("Actualizar", "actualizar", self.al_mostrar)):
            b = QPushButton(" " + texto, objectName="chico")
            b.setIcon(iconos.icono(ic, tema.TEXTO))
            b.clicked.connect(funcion)
            self.acciones.addWidget(b)

        # ---- cifras
        fila = QHBoxLayout()
        self.cifras = {}
        for clave, titulo, ic in (("victorias", "Victorias", "trofeo"), ("oro", "Oro", "oro"),
                                  ("objetos", "Objetos conseguidos", "objetos"), ("distintos", "Objetos distintos", "distintos")):
            marco, cifra = tarjeta(titulo, icono=ic)
            self.cifras[clave] = cifra
            fila.addWidget(marco)
        self.cuerpo.addLayout(fila)

        # ---- filtro
        filtro = QHBoxLayout()
        filtro.addWidget(QLabel("Mostrar:"))
        self.combo = QComboBox()
        self.combo.setMinimumWidth(320)
        self.combo.currentIndexChanged.connect(self._pintar)
        filtro.addWidget(self.combo)
        filtro.addStretch()
        self.cuerpo.addLayout(filtro)

        # ---- aviso de objetos sin nombre
        self.aviso = QFrame(objectName="aviso")
        capa_aviso = QHBoxLayout(self.aviso)
        self.aviso_txt = QLabel(wordWrap=True)
        capa_aviso.addWidget(self.aviso_txt)
        self.cuerpo.addWidget(self.aviso)

        # ---- pestanas: Botin / Fotos
        self.pestanas = QTabWidget()
        self.pestanas.addTab(self._crear_botin(), iconos.icono("recompensas", tema.TENUE), " Botín")
        self.pestanas.addTab(self._crear_fotos(), iconos.icono("foto", tema.TENUE), " Fotos")
        self.cuerpo.addWidget(self.pestanas, 1)

        app.puente.stats.connect(self._quizas_nueva_foto)
        self._ultimas_fotos = 0
        self.al_mostrar()

    # ------------------------------------------------------------------ construccion
    def _crear_botin(self) -> QWidget:
        desplazable = QScrollArea(widgetResizable=True)
        contenido = QWidget()
        self.rejilla_botin = QGridLayout(contenido)
        self.rejilla_botin.setContentsMargins(10, 10, 10, 10)
        self.rejilla_botin.setSpacing(10)
        self.rejilla_botin.setAlignment(Qt.AlignTop)
        desplazable.setWidget(contenido)
        return desplazable

    def _crear_fotos(self) -> QWidget:
        w = QWidget()
        abajo = QHBoxLayout(w)
        self.galeria = QListWidget()
        self.galeria.setViewMode(QListView.IconMode)
        self.galeria.setResizeMode(QListView.Adjust)
        self.galeria.setMovement(QListView.Static)
        self.galeria.setIconSize(QSize(ANCHO_MINIATURA, int(ANCHO_MINIATURA * 16 / 9)))
        self.galeria.setGridSize(QSize(ANCHO_MINIATURA + 24, int(ANCHO_MINIATURA * 16 / 9) + 44))
        self.galeria.setUniformItemSizes(True)
        self.galeria.currentItemChanged.connect(self._seleccionar)
        self.galeria.itemDoubleClicked.connect(lambda _: self._abrir_imagen())
        abajo.addWidget(self.galeria, 1)
        detalle = QVBoxLayout()
        self.grande = QLabel("Elige una foto", objectName="vista", alignment=Qt.AlignCenter)
        self.grande.setFixedSize(160, 284)
        detalle.addWidget(self.grande)
        self.info = QLabel(objectName="tenue", wordWrap=True)
        self.info.setFixedWidth(200)
        detalle.addWidget(self.info)
        self.b_abrir = QPushButton("Abrir imagen")
        self.b_abrir.clicked.connect(self._abrir_imagen)
        detalle.addWidget(self.b_abrir)
        detalle.addStretch()
        abajo.addLayout(detalle)
        return w

    # ----------------------------------------------------------------- datos
    def al_mostrar(self):
        self.registros = recompensas.leer()
        if any(not r.get("analizado") for r in self.registros):
            recompensas.reanalizar_pendientes()  # fotos de antes de que existiera la lectura
            self.registros = recompensas.leer()
        inicio_hoy = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
        sesiones: dict[float, list[dict]] = {}
        for r in self.registros:
            sesiones.setdefault(r.get("sesion", 0), []).append(r)
        elegido = self.combo.currentData()
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem("Todo", ("todas", None))
        self.combo.addItem("Hoy", ("hoy", inicio_hoy))
        for inicio, lista in sorted(sesiones.items(), key=lambda kv: -kv[0]):
            fecha = time.strftime("%d/%m %H:%M", time.localtime(inicio))
            self.combo.addItem(f"Sesion {fecha} · {lista[0].get('nombre_modo', lista[0]['modo'])} ({len(lista)})", ("sesion", inicio))
        indice = self.combo.findData(elegido) if elegido else 0
        self.combo.setCurrentIndex(max(0, indice))
        self.combo.blockSignals(False)
        self._pintar()

    def _filtrados(self) -> list[dict]:
        tipo, valor = self.combo.currentData() or ("todas", None)
        if tipo == "hoy":
            return [r for r in self.registros if r["fecha"] >= valor]
        if tipo == "sesion":
            return [r for r in self.registros if r.get("sesion") == valor]
        return self.registros

    def _pintar(self):
        filtrados = self._filtrados()
        catalogo = botin.cargar_catalogo()
        totales = recompensas.totales_objetos(filtrados)
        self.cifras["victorias"].setText(str(len(filtrados)))
        self.cifras["oro"].setText(_miles(recompensas.total_oro(filtrados)))
        self.cifras["objetos"].setText(_miles(sum(totales.values())))
        self.cifras["distintos"].setText(str(len(totales)))

        sin_nombre = [oid for oid in totales if not (catalogo.get(oid) or {}).get("nombre")]
        self.aviso.setVisible(bool(sin_nombre))
        self.aviso_txt.setText(
            f"<b>{len(sin_nombre)} objeto(s) sin nombre</b> (borde punteado). Haz doble clic en ellos para "
            "ponerles nombre; después se reconocen solos.")

        while self.rejilla_botin.count():
            w = self.rejilla_botin.takeAt(0).widget()
            if w:
                w.setParent(None)
        for i, (oid, total) in enumerate(totales.items()):
            veces = sum(1 for r in filtrados if oid in (r.get("objetos") or {}))
            casilla = CasillaObjeto(oid, botin.nombre(oid, catalogo), total,
                                    f"{total / len(filtrados):.1f}" if filtrados else "—",
                                    f"en {veces} de {len(filtrados)} victorias", oid in sin_nombre)
            casilla.renombrar.connect(self._renombrar)
            self.rejilla_botin.addWidget(casilla, i // COLUMNAS_BOTIN, i % COLUMNAS_BOTIN)
        if not totales:
            vacio = QLabel("Todavía no hay recompensas: se guardan solas cada vez que el bot gana.",
                           objectName="tenue", alignment=Qt.AlignCenter)
            self.rejilla_botin.addWidget(vacio, 0, 0, 1, COLUMNAS_BOTIN)
        self._pintar_galeria(filtrados)

    def _renombrar(self, oid: str):
        catalogo = botin.cargar_catalogo()
        actual = (catalogo.get(oid) or {}).get("nombre", "")
        nombre, ok = QInputDialog.getText(self, "Nombre del objeto", "¿Que objeto es? (p. ej. 'Cubo de mejora gris'):", text=actual)
        if ok:
            catalogo.setdefault(oid, {})["nombre"] = nombre.strip()
            botin.guardar_catalogo(catalogo)
            self._pintar()

    def _reanalizar(self):
        hechas = recompensas.reanalizar_pendientes(todas=True)
        self.al_mostrar()
        self.aviso_txt.setText(self.aviso_txt.text() + f"  (Analizadas de nuevo: {hechas} fotos.)")

    # ------------------------------------------------------------------ fotos
    def _miniatura(self, registro: dict) -> QIcon:
        clave = registro["ruta"]
        if clave not in self._miniaturas:
            pix = QPixmap(str(registro["ruta_completa"]))
            self._miniaturas[clave] = QIcon(pix.scaledToWidth(ANCHO_MINIATURA, Qt.SmoothTransformation))
        return self._miniaturas[clave]

    def _pintar_galeria(self, filtrados: list[dict]):
        self.galeria.clear()
        for r in filtrados[:MAXIMO_EN_GALERIA]:
            hora = time.strftime("%d/%m %H:%M", time.localtime(r["fecha"]))
            item = QListWidgetItem(self._miniatura(r), f"#{r.get('victoria', '?')} · {hora}")
            item.setData(Qt.UserRole, r)
            item.setTextAlignment(Qt.AlignHCenter)
            self.galeria.addItem(item)
        if self.galeria.count():
            self.galeria.setCurrentRow(0)
        else:
            self._seleccionar(None, None)
            self.grande.setText("Todavia no hay fotos.\nSe guardan solas al ganar.")

    def _seleccionar(self, actual, _anterior=None):
        self.seleccion = actual.data(Qt.UserRole) if actual else None
        self.b_abrir.setEnabled(self.seleccion is not None)
        if not self.seleccion:
            self.grande.clear()
            self.info.setText("")
            return
        r = self.seleccion
        pix = QPixmap(str(r["ruta_completa"]))
        self.grande.setPixmap(pix.scaled(self.grande.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        catalogo = botin.cargar_catalogo()
        objetos = ", ".join(f"{botin.nombre(oid, catalogo)} x{n}" for oid, n in (r.get("objetos") or {}).items())
        self.info.setText(
            f"Victoria #{r.get('victoria', '?')} · {time.strftime('%d/%m/%Y %H:%M', time.localtime(r['fecha']))}<br>"
            f"{r.get('nombre_modo', r['modo'])}<br>Oro: {_miles(int(r.get('oro') or 0))}<br>{objetos}"
        )

    def _abrir_imagen(self):
        if self.seleccion:
            os.startfile(self.seleccion["ruta_completa"])

    def _abrir_carpeta(self):
        recompensas.CARPETA.mkdir(parents=True, exist_ok=True)
        os.startfile(recompensas.CARPETA)

    def _quizas_nueva_foto(self, stats: dict):
        """Si el bot guardo una foto nueva y la pagina esta a la vista, refrescarla."""
        fotos = stats.get("fotos_recompensas", 0)
        if fotos != self._ultimas_fotos:
            self._ultimas_fotos = fotos
            if self.isVisible():
                self.al_mostrar()

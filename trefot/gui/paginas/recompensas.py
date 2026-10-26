"""Pagina Recompensas: galeria de las pantallas de recompensas guardadas al ganar."""

import os
import time

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from trefot import recompensas
from trefot.gui.comun import Pagina, tarjeta

MAXIMO_EN_GALERIA = 400
ANCHO_MINIATURA = 110


class PaginaRecompensas(Pagina):
    titulo = "Recompensas"
    subtitulo = (
        "Cada victoria guarda una foto de la pantalla de recompensas. "
        "Mas adelante el bot reconocera los objetos y aqui veras los totales."
    )

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.registros: list[dict] = []
        self.seleccion: dict | None = None
        self._miniaturas: dict[str, QIcon] = {}

        b_carpeta = QPushButton("Abrir carpeta")
        b_carpeta.clicked.connect(self._abrir_carpeta)
        b_refrescar = QPushButton("Actualizar")
        b_refrescar.clicked.connect(self.al_mostrar)
        self.acciones.addWidget(b_carpeta)
        self.acciones.addWidget(b_refrescar)

        # ---- cifras
        fila = QHBoxLayout()
        self.cifras = {}
        for clave, titulo in (("total", "Fotos guardadas"), ("hoy", "Hoy"), ("sesiones", "Sesiones"), ("mostradas", "En pantalla")):
            marco, cifra = tarjeta(titulo)
            self.cifras[clave] = cifra
            fila.addWidget(marco)
        self.cuerpo.addLayout(fila)

        # ---- filtro
        filtro = QHBoxLayout()
        filtro.addWidget(QLabel("Mostrar:"))
        self.combo = QComboBox()
        self.combo.setMinimumWidth(320)
        self.combo.currentIndexChanged.connect(self._pintar_galeria)
        filtro.addWidget(self.combo)
        filtro.addStretch()
        self.cuerpo.addLayout(filtro)

        # ---- galeria + detalle
        abajo = QHBoxLayout()
        self.galeria = QListWidget()
        self.galeria.setViewMode(QListView.IconMode)
        self.galeria.setResizeMode(QListView.Adjust)
        self.galeria.setMovement(QListView.Static)
        self.galeria.setIconSize(QSize(ANCHO_MINIATURA, int(ANCHO_MINIATURA * 16 / 9)))
        self.galeria.setGridSize(QSize(ANCHO_MINIATURA + 24, int(ANCHO_MINIATURA * 16 / 9) + 44))
        self.galeria.setSpacing(6)
        self.galeria.setUniformItemSizes(True)
        self.galeria.currentItemChanged.connect(self._seleccionar)
        self.galeria.itemDoubleClicked.connect(lambda _: self._abrir_imagen())
        abajo.addWidget(self.galeria, 1)

        detalle = QVBoxLayout()
        self.grande = QLabel("Elige una foto", objectName="vista", alignment=Qt.AlignCenter)
        self.grande.setFixedSize(198, 352)
        detalle.addWidget(self.grande)
        detalle.addSpacing(6)
        self.info = QLabel(objectName="tenue", wordWrap=True)
        detalle.addWidget(self.info)
        self.b_abrir = QPushButton("Abrir imagen")
        self.b_abrir.clicked.connect(self._abrir_imagen)
        self.b_abrir.setEnabled(False)
        detalle.addWidget(self.b_abrir)
        detalle.addStretch()
        abajo.addLayout(detalle)
        self.cuerpo.addLayout(abajo, 1)

        # ---- objetos (se rellena cuando exista el reconocimiento)
        self.grupo_objetos = QGroupBox("Objetos conseguidos")
        capa = QVBoxLayout(self.grupo_objetos)
        self.objetos = QLabel(objectName="tenue", wordWrap=True)
        capa.addWidget(self.objetos)
        self.cuerpo.addWidget(self.grupo_objetos)

        app.puente.stats.connect(self._quizas_nueva_foto)
        self._ultimas_fotos = 0
        self.al_mostrar()

    # ----------------------------------------------------------------- datos
    def al_mostrar(self):
        self.registros = recompensas.leer()
        inicio_hoy = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
        sesiones: dict[float, list[dict]] = {}
        for r in self.registros:
            sesiones.setdefault(r.get("sesion", 0), []).append(r)

        self.cifras["total"].setText(str(len(self.registros)))
        self.cifras["hoy"].setText(str(sum(1 for r in self.registros if r["fecha"] >= inicio_hoy)))
        self.cifras["sesiones"].setText(str(len(sesiones)))

        elegido = self.combo.currentData()
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem("Todas", ("todas", None))
        self.combo.addItem("Hoy", ("hoy", inicio_hoy))
        for inicio, lista in sorted(sesiones.items(), key=lambda kv: -kv[0]):  # la sesion mas reciente primero
            fecha = time.strftime("%d/%m %H:%M", time.localtime(inicio))
            self.combo.addItem(f"Sesion {fecha} · {lista[0].get('nombre_modo', lista[0]['modo'])} ({len(lista)})", ("sesion", inicio))
        indice = self.combo.findData(elegido) if elegido else 0
        self.combo.setCurrentIndex(max(0, indice))
        self.combo.blockSignals(False)
        self._pintar_galeria()

    def _filtrados(self) -> list[dict]:
        tipo, valor = self.combo.currentData() or ("todas", None)
        if tipo == "hoy":
            return [r for r in self.registros if r["fecha"] >= valor]
        if tipo == "sesion":
            return [r for r in self.registros if r.get("sesion") == valor]
        return self.registros

    def _miniatura(self, registro: dict) -> QIcon:
        clave = registro["ruta"]
        if clave not in self._miniaturas:
            pix = QPixmap(str(registro["ruta_completa"]))
            self._miniaturas[clave] = QIcon(pix.scaledToWidth(ANCHO_MINIATURA, Qt.SmoothTransformation))
        return self._miniaturas[clave]

    def _pintar_galeria(self):
        filtrados = self._filtrados()
        self.galeria.clear()
        for r in filtrados[:MAXIMO_EN_GALERIA]:
            hora = time.strftime("%d/%m %H:%M", time.localtime(r["fecha"]))
            item = QListWidgetItem(self._miniatura(r), f"#{r.get('victoria', '?')} · {hora}")
            item.setData(Qt.UserRole, r)
            item.setTextAlignment(Qt.AlignHCenter)
            self.galeria.addItem(item)
        self.cifras["mostradas"].setText(str(min(len(filtrados), MAXIMO_EN_GALERIA)))
        if self.galeria.count():
            self.galeria.setCurrentRow(0)
        else:
            self._seleccionar(None, None)
            self.grande.setText("Todavia no hay fotos.\nSe guardan solas al ganar.")
        self._pintar_objetos(filtrados)

    def _pintar_objetos(self, filtrados: list[dict]):
        totales = recompensas.totales_objetos(filtrados)
        if totales:
            self.objetos.setText("   ".join(f"<b>{n}</b>: {c}" for n, c in totales.items()))
        else:
            self.objetos.setText(
                "Aun no se reconocen los objetos: por ahora solo se guardan las fotos. "
                "Cuando el reconocimiento este listo, aqui saldran los totales por objeto de lo que elijas arriba."
            )

    # ------------------------------------------------------------- seleccion
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
        self.info.setText(
            f"Victoria #{r.get('victoria', '?')} de la sesion<br>"
            f"{time.strftime('%d/%m/%Y %H:%M:%S', time.localtime(r['fecha']))}<br>"
            f"{r.get('nombre_modo', r['modo'])}"
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

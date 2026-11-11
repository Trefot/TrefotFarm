"""Reproductor integrado en Farmear: secuencia manual y analisis en segundo plano."""

import threading
from pathlib import Path

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from lumen import admin, reproductor
from lumen.gui.comun import a_pixmap


class _Senales(QObject):
    terminado = pyqtSignal(object, str)


class VistaCaptura(QLabel):
    def __init__(self):
        super().__init__(
            "Abre capturas de la ventana del juego\n550 × 940 px",
            alignment=Qt.AlignCenter,
        )
        self.setMinimumSize(180, 240)
        self._original = None

    def limpiar(self):
        self._original = None
        self.setText("Sin imagen disponible")

    def mostrar(self, imagen):
        self._original = a_pixmap(imagen)
        self._ajustar()

    def _ajustar(self):
        if self._original is not None:
            self.setPixmap(
                self._original.scaled(
                    self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self._ajustar()


class PanelReproductor(QFrame):
    def __init__(self, contexto, bloqueado):
        super().__init__(objectName="seccion")
        self.contexto, self.bloqueado = contexto, bloqueado
        self.rutas, self.indice = [], 0
        self.ocupado = False
        self.resultado = None
        self.senales = _Senales(self)
        self.senales.terminado.connect(self._terminado)
        capa = QVBoxLayout(self)
        capa.addWidget(
            QLabel("Revisar capturas · IA general", objectName="titulo_seccion")
        )
        capa.addWidget(
            QLabel(
                "Cada imagen es independiente. No ejecuta clics ni reproduce el guion del modo.",
                wordWrap=True,
            )
        )
        fila = QHBoxLayout()
        self.abrir = QPushButton("Abrir capturas")
        self.abrir.clicked.connect(self._abrir)
        self.anterior = QPushButton("←")
        self.siguiente = QPushButton("→")
        self.anterior.clicked.connect(lambda: self.mover(-1))
        self.siguiente.clicked.connect(lambda: self.mover(1))
        self.posicion = QLabel("Sin capturas")
        for w in (self.abrir, self.anterior, self.siguiente, self.posicion):
            fila.addWidget(w)
        fila.addStretch()
        capa.addLayout(fila)
        opciones = QHBoxLayout()
        self.fase = QSpinBox(minimum=1, maximum=4, value=1)
        self.piso = QSpinBox(minimum=1, maximum=3, value=1)
        self.acciones = QSpinBox(minimum=0, maximum=6, value=0)
        self.acciones.setSpecialValueText("Detectar")
        self.analizar = QPushButton("Analizar", objectName="primario")
        self.analizar.clicked.connect(self.revisar)
        for titulo, campo in (
            ("Piso F1–3", self.piso),
            ("Fase", self.fase),
            ("Acciones", self.acciones),
        ):
            opciones.addWidget(QLabel(titulo))
            opciones.addWidget(campo)
        opciones.addWidget(self.analizar)
        capa.addLayout(opciones)
        fila_equipo = QHBoxLayout()
        fila_equipo.addWidget(QLabel("Equipo para comparar memoria"))
        self.equipo = QLineEdit()
        self.equipo.setPlaceholderText(
            "IDs: odin, gawain, freyja_roja, thonar_azul (vacío = sin memoria)"
        )
        fila_equipo.addWidget(self.equipo, 1)
        capa.addLayout(fila_equipo)
        self.estado = QLabel(
            "El contexto se toma del modo seleccionado arriba. Detén el bot antes de analizar.",
            wordWrap=True,
        )
        capa.addWidget(self.estado)
        cuerpo = QHBoxLayout()
        self.vista = VistaCaptura()
        self.detalle = QTextEdit(readOnly=True)
        self.detalle.setPlaceholderText(
            "Aquí verás la mano reconocida y la propuesta de la IA."
        )
        cuerpo.addWidget(self.vista, 1)
        cuerpo.addWidget(self.detalle, 2)
        capa.addLayout(cuerpo, 1)
        self.copiar = QPushButton("Copiar análisis")
        self.copiar.clicked.connect(self._copiar)
        capa.addWidget(self.copiar)
        self._botones()

    def _botones(self):
        self.abrir.setEnabled(not self.ocupado)
        self.anterior.setEnabled(not self.ocupado and self.indice > 0)
        self.siguiente.setEnabled(
            not self.ocupado and self.indice < len(self.rutas) - 1
        )
        self.analizar.setEnabled(bool(self.rutas) and not self.ocupado)
        self.copiar.setEnabled(self.resultado is not None and not self.ocupado)
        for campo in (self.fase, self.piso, self.acciones, self.equipo):
            campo.setEnabled(not self.ocupado)

    def _abrir(self):
        if not admin.activo():
            self.revocar()
            return
        rutas, _ = QFileDialog.getOpenFileNames(
            self, "Capturas del juego", "", "Imágenes (*.png *.jpg *.jpeg)"
        )
        if rutas:
            self.cargar(rutas)

    def cargar(self, rutas):
        if not admin.activo():
            self.revocar()
            return
        if self.ocupado:
            return
        self.rutas, self.indice = reproductor.ordenar(rutas), 0
        self._seleccionar()

    def mover(self, paso):
        if self.ocupado or not 0 <= self.indice + paso < len(self.rutas):
            return
        self.indice += paso
        self._seleccionar()

    def _seleccionar(self):
        self.resultado = None
        self.detalle.clear()
        if self.rutas:
            ruta = self.rutas[self.indice]
            self.posicion.setText(f"{self.indice + 1}/{len(self.rutas)} · {ruta.name}")
            self.posicion.setToolTip(str(ruta))
            from lumen.vision import leer_imagen

            imagen = leer_imagen(ruta)
            if imagen is not None:
                self.vista.mostrar(imagen)
                self.estado.setText(
                    "Captura cargada. Elige piso, fase y acciones; después pulsa Analizar."
                )
            else:
                self.vista.limpiar()
                self.estado.setText("No se pudo leer esta imagen.")
        self._botones()

    def revisar(self):
        if not admin.activo():
            self.revocar()
            return
        if self.ocupado or not self.rutas:
            return
        if self.bloqueado():
            self.estado.setText(
                "Detén el bot y el plan del día antes de analizar capturas."
            )
            return
        destino, demonio = self.contexto()
        if destino.endswith("_pisos1a3"):
            destino = destino.replace("_pisos1a3", f"_f{self.piso.value()}")
        ruta = Path(self.rutas[self.indice])
        opciones = dict(
            destino=destino,
            demonio=demonio,
            fase=self.fase.value(),
            acciones=self.acciones.value(),
            equipo=[p.strip() for p in self.equipo.text().split(",") if p.strip()],
        )
        self.ocupado, self.resultado = True, None
        self.detalle.clear()
        self.estado.setText("Reconociendo cartas y calculando la propuesta…")
        self._botones()

        def trabajar():
            resultado, error = None, ""
            try:
                resultado = reproductor.analizar(ruta, **opciones)
            except Exception as fallo:
                error = str(fallo)
            try:
                self.senales.terminado.emit(resultado, error)
            except RuntimeError:
                pass  # la interfaz ya se cerro

        threading.Thread(target=trabajar, daemon=True, name="reproductor").start()

    def _terminado(self, resultado, error):
        if not admin.activo():
            self.ocupado = False
            self.revocar()
            return
        self.ocupado, self.resultado = False, resultado
        if error:
            self.estado.setText(error)
        else:
            self.estado.setText(
                "Análisis listo · amarillo: propuesta · verde: jugable · rojo: no jugable"
            )
            self.vista.mostrar(reproductor.anotar(resultado))
            self.detalle.setPlainText(resultado.texto())
        self._botones()

    def _copiar(self):
        if admin.activo():
            QApplication.clipboard().setText(self.detalle.toPlainText())
        else:
            self.revocar()

    def revocar(self):
        self.rutas, self.indice, self.resultado = [], 0, None
        self.detalle.clear()
        self.equipo.clear()
        self.vista.limpiar()
        self.posicion.setText("Acceso restringido")
        self.estado.setText("Desbloquea el modo administrador en Ajustes.")
        self._botones()

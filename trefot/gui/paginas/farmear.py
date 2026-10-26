"""Pagina Farmear: elegir modo, opciones, controles, registro y vista en vivo."""

import time

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from trefot import config, ventana
from trefot.control import control
from trefot.gui import tema
from trefot.gui.comun import Pagina, a_pixmap, dibujar_regiones, formatear_tiempo, tarjeta
from trefot.modos import MODOS


class PaginaFarmear(Pagina):
    titulo = "Farmear"
    subtitulo = "Elige el modo, ajusta las opciones y pulsa Iniciar. El juego debe estar visible."

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.puente = app.puente
        self.campos = {}
        self.inicio = None
        self.ultimas_stats: dict = {}

        fila = QHBoxLayout()
        fila.setSpacing(14)

        # ---- columna izquierda
        izq = QVBoxLayout()
        grupo_modo = QGroupBox("Modo")
        capa_modo = QVBoxLayout(grupo_modo)
        self.combo = QComboBox()
        for modo in MODOS.values():
            self.combo.addItem(modo.nombre, modo.id)
        self.combo.setCurrentIndex(max(0, self.combo.findData(config.obtener("ultimo_modo"))))
        self.descripcion = QLabel(wordWrap=True, objectName="tenue")
        self.form = QFormLayout()
        capa_modo.addWidget(self.combo)
        capa_modo.addWidget(self.descripcion)
        capa_modo.addLayout(self.form)
        izq.addWidget(grupo_modo)

        botones = QHBoxLayout()
        self.b_iniciar = QPushButton("▶  Iniciar", objectName="iniciar")
        self.b_pausar = QPushButton("❚❚  Pausar", objectName="pausar")
        self.b_detener = QPushButton("■  Detener", objectName="detener")
        for b in (self.b_iniciar, self.b_pausar, self.b_detener):
            b.setMinimumHeight(40)
            botones.addWidget(b)
        izq.addLayout(botones)
        self.ayuda_teclas = QLabel(objectName="tenue", wordWrap=True)
        izq.addWidget(self.ayuda_teclas)

        grupo_stats = QGroupBox("Sesion actual")
        rejilla = QGridLayout(grupo_stats)
        self.cifras = {}
        for i, (clave, titulo) in enumerate(
            [("victorias", "Victorias"), ("derrotas", "Derrotas"), ("reinicios", "Reinicios"),
             ("tasa", "% exito"), ("pociones", "Pociones"), ("tiempo", "Tiempo")]
        ):
            marco, cifra = tarjeta(titulo)
            self.cifras[clave] = cifra
            rejilla.addWidget(marco, i // 3, i % 3)
        self.lbl_estado = QLabel("Estado: detenido", objectName="tenue")
        rejilla.addWidget(self.lbl_estado, 2, 0, 1, 3)
        izq.addWidget(grupo_stats)
        izq.addStretch()

        # ---- centro: registro
        centro = QVBoxLayout()
        cabecera = QHBoxLayout()
        cabecera.addWidget(QLabel("<b>Registro</b>"))
        cabecera.addStretch()
        self.chk_debug = QCheckBox("Detalle")
        cabecera.addWidget(self.chk_debug)
        b_limpiar = QPushButton("Limpiar")
        b_limpiar.clicked.connect(lambda: self.registro.clear())
        cabecera.addWidget(b_limpiar)
        centro.addLayout(cabecera)
        self.registro = QTextEdit(readOnly=True, objectName="registro")
        centro.addWidget(self.registro)

        # ---- derecha: vista previa
        der = QVBoxLayout()
        cab_vista = QHBoxLayout()
        self.chk_vista = QCheckBox("Vista en vivo", checked=True)
        self.chk_regiones = QCheckBox("Regiones")
        cab_vista.addWidget(self.chk_vista)
        cab_vista.addWidget(self.chk_regiones)
        der.addLayout(cab_vista)
        self.vista = QLabel("Sin juego", objectName="vista", alignment=Qt.AlignCenter)
        self.vista.setFixedSize(262, 466)
        der.addWidget(self.vista)
        der.addStretch()

        fila.addLayout(izq, 3)
        fila.addLayout(centro, 5)
        fila.addLayout(der, 0)
        self.cuerpo.addLayout(fila)

        self.combo.currentIndexChanged.connect(self._mostrar_opciones)
        self.b_iniciar.clicked.connect(self.iniciar)
        self.b_pausar.clicked.connect(self.pausar)
        self.b_detener.clicked.connect(self.detener)
        self.puente.log.connect(self.escribir)
        self.puente.estado.connect(lambda e: self.lbl_estado.setText(f"Estado: {e}"))
        self.puente.stats.connect(self._stats)
        self.puente.terminado.connect(self._terminado)
        self.puente.tecla.connect(self._tecla)

        self.temporizador = QTimer(self, timeout=self._refrescar)
        self.ajustar_fps()
        self._mostrar_opciones()
        self._botones(False)
        self.actualizar_ayuda_teclas()

    # ------------------------------------------------------------------ opciones
    @property
    def modo_cls(self):
        return MODOS[self.combo.currentData()]

    def _mostrar_opciones(self):
        while self.form.rowCount():
            self.form.removeRow(0)
        self.campos = {}
        cls = self.modo_cls
        self.descripcion.setText(cls.descripcion)
        guardadas = (config.obtener("opciones_modos") or {}).get(cls.id, {})
        for op in cls.opciones:
            valor = guardadas.get(op.clave, op.defecto)
            if op.tipo == "entero":
                campo = QSpinBox(minimum=op.minimo, maximum=op.maximo, value=int(valor))
            elif op.tipo == "si_no":
                campo = QCheckBox(checked=bool(valor))
            elif op.tipo == "lista":
                campo = QComboBox()
                campo.addItems([str(x) for x in op.opciones])
                campo.setCurrentText(str(valor))
            else:
                campo = QLineEdit(str(valor))
            campo.setToolTip(op.ayuda)
            self.campos[op.clave] = campo
            self.form.addRow(op.etiqueta, campo)

    def _valores(self) -> dict:
        valores = {}
        for clave, campo in self.campos.items():
            if isinstance(campo, QSpinBox):
                valores[clave] = campo.value()
            elif isinstance(campo, QCheckBox):
                valores[clave] = campo.isChecked()
            elif isinstance(campo, QComboBox):
                valores[clave] = campo.currentText()
            else:
                valores[clave] = campo.text()
        return valores

    # ------------------------------------------------------------------ control
    def iniciar(self):
        if self.app.update_bloqueante:
            self.app.mostrar_bloqueo()
            return
        cls = self.modo_cls
        equipo = getattr(cls, "equipo", None)
        if equipo is not None:
            equipo.recargar()
            faltan = equipo.faltantes()
            if faltan:
                r = QMessageBox.warning(
                    self, "Faltan capturas",
                    "Antes de farmear saca estas capturas:\n\n" + "\n".join(f"• {d.descripcion}" for d in faltan)
                    + "\n\n¿Ir a la pagina Capturas?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if r == QMessageBox.Yes:
                    self.app.navegar("capturas")
                return
        if not ventana.ventana_abierta():
            QMessageBox.warning(self, "Juego cerrado", f"No encuentro la ventana '{config.obtener('titulo_ventana')}'.")
            return
        if not ventana.ajustar_tamano():
            self.escribir("No pude dejar la ventana en 540x960 exacto; puede fallar el reconocimiento.", "aviso")
        ventana.traer_al_frente()
        valores = self._valores()
        opciones = dict(config.obtener("opciones_modos") or {})
        opciones[cls.id] = valores
        config.guardar({"opciones_modos": opciones, "ultimo_modo": cls.id})
        for cifra in self.cifras.values():
            cifra.setText("0")
        self.ultimas_stats = {}
        self.inicio = time.time()
        self.puente.iniciar(cls(valores))
        self._botones(True)
        self.app.navegar("farmear")

    def pausar(self):
        if not self.puente.corriendo:
            return
        if control.en_pausa:
            ventana.traer_al_frente()
            control.reanudar()
            self.b_pausar.setText("❚❚  Pausar")
        else:
            control.pausar()
            self.b_pausar.setText("▶  Reanudar")

    def detener(self):
        control.detener()
        self.b_pausar.setText("❚❚  Pausar")

    def _tecla(self, cual: str):
        if cual == "pausa":
            self.pausar()
        elif cual == "detener":
            self.detener()

    def _terminado(self):
        self._botones(False)
        self.lbl_estado.setText("Estado: detenido")
        self.inicio = None

    def _botones(self, corriendo: bool):
        self.b_iniciar.setEnabled(not corriendo)
        self.b_pausar.setEnabled(corriendo)
        self.b_detener.setEnabled(corriendo)
        self.combo.setEnabled(not corriendo)
        for campo in self.campos.values():
            campo.setEnabled(not corriendo)

    def actualizar_ayuda_teclas(self):
        self.ayuda_teclas.setText(
            f"{str(config.obtener('tecla_pausa')).upper()} pausa · {str(config.obtener('tecla_detener')).upper()} detener · "
            "raton a una esquina = freno de emergencia. Mientras corre, no muevas el raton."
        )

    def ajustar_fps(self):
        self.temporizador.start(int(1000 / max(1, int(config.obtener("fps_vista_previa")))))

    # --------------------------------------------------------------- registro
    def escribir(self, mensaje: str, nivel: str = "info"):
        if nivel == "debug" and not self.chk_debug.isChecked():
            return
        color = tema.COLOR_NIVEL.get(nivel, tema.TEXTO)
        hora = time.strftime("%H:%M:%S")
        texto = mensaje.replace("&", "&amp;").replace("<", "&lt;")
        self.registro.append(f'<span style="color:{tema.TENUE}">{hora}</span> <span style="color:{color}">{texto}</span>')
        self.registro.moveCursor(QTextCursor.End)
        if self.registro.document().blockCount() > 3000:
            cursor = self.registro.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.removeSelectedText()

    def _stats(self, s: dict):
        self.ultimas_stats = s
        for clave in ("victorias", "derrotas", "reinicios", "pociones"):
            if clave in s:
                self.cifras[clave].setText(str(s[clave]))
        if "tasa" in s:
            self.cifras["tasa"].setText(f"{s['tasa']:.0f}%")

    def _refrescar(self):
        if self.inicio:
            self.cifras["tiempo"].setText(formatear_tiempo(time.time() - self.inicio))
        if not self.chk_vista.isChecked() or not self.isVisible():
            return
        try:
            pantalla, _ = ventana.capturar()
        except Exception:
            self.vista.setText("Sin juego")
            return
        if self.chk_regiones.isChecked():
            pantalla = dibujar_regiones(pantalla)
        self.vista.setPixmap(a_pixmap(pantalla).scaled(self.vista.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

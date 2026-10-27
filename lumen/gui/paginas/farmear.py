"""Pagina Farmear: el modo y sus opciones, los controles, que esta haciendo el bot y el registro."""

import time

from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
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

from lumen import actualizador, avisos, config, ordenes, ventana
from lumen.control import control
from lumen.gui import iconos, tema
from lumen.gui.comun import Pagina, formatear_tiempo, tarjeta
from lumen.modos import MODOS
from lumen.rutas import IMAGENES

CIFRAS = [("victorias", "Victorias", "trofeo"), ("derrotas", "Derrotas", "derrota"), ("reinicios", "Reinicios", "reinicio"),
          ("tasa", "% de éxito", "tasa"), ("pociones", "Pociones", "pocion"), ("tiempo", "Tiempo", "reloj")]


def _repintar(widget, propiedad: str, valor):
    widget.setProperty(propiedad, valor)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class PaginaFarmear(Pagina):
    titulo = "Farmear"
    subtitulo = "Elige el modo y pulsa Iniciar. El juego debe estar abierto y visible."

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.puente = app.puente
        self.campos = {}
        self.inicio = None
        self.ultimas_stats: dict = {}
        self.estado_bot = ""
        self.fases: list[QLabel] = []
        self.modo_externo = None  # una herramienta (p. ej. la captura de heroes) en vez del modo elegido

        fila = QHBoxLayout()
        fila.setSpacing(16)

        # ---- columna izquierda: modo, opciones y controles
        izq = QVBoxLayout()
        izq.setSpacing(12)
        grupo_modo = QGroupBox("Misión")
        capa_modo = QVBoxLayout(grupo_modo)
        capa_modo.setSpacing(8)
        cabecera_modo = QHBoxLayout()
        self.emblema = QLabel()
        self.emblema.setFixedSize(68, 68)
        cabecera_modo.addWidget(self.emblema)
        textos = QVBoxLayout()
        textos.setSpacing(0)
        self.nombre_modo = QLabel(objectName="titulo_tarjeta", wordWrap=True)
        self.sub_modo = QLabel(objectName="tenue")
        textos.addWidget(self.nombre_modo)
        textos.addWidget(self.sub_modo)
        cabecera_modo.addLayout(textos, 1)
        capa_modo.addLayout(cabecera_modo)
        self.combo = QComboBox()
        for modo in MODOS.values():
            self.combo.addItem(modo.nombre, modo.id)
        self.combo.setCurrentIndex(max(0, self.combo.findData(config.obtener("ultimo_modo"))))
        self.combo.setVisible(len(MODOS) > 1)
        capa_modo.addWidget(self.combo)
        self.descripcion = QLabel(wordWrap=True, objectName="tenue")
        capa_modo.addWidget(self.descripcion)
        self.form = QFormLayout()
        capa_modo.addLayout(self.form)
        izq.addWidget(grupo_modo)

        botones = QHBoxLayout()
        self.b_iniciar = QPushButton(" Iniciar", objectName="iniciar")
        self.b_pausar = QPushButton(" Pausar", objectName="pausar")
        self.b_detener = QPushButton(" Detener", objectName="detener")
        for b, ic in ((self.b_iniciar, "jugar"), (self.b_pausar, "pausa"), (self.b_detener, "detener")):
            b.setIcon(iconos.icono(ic, tema.TEXTO))
            b.setIconSize(QSize(18, 18))
            b.setMinimumHeight(42)
            b.setCursor(Qt.PointingHandCursor)
            botones.addWidget(b)
        izq.addLayout(botones)
        self.ayuda_teclas = QLabel(objectName="tenue", wordWrap=True)
        izq.addWidget(self.ayuda_teclas)
        izq.addStretch()

        # ---- columna derecha: que esta pasando, cifras y registro
        der = QVBoxLayout()
        der.setSpacing(12)
        ahora = QFrame(objectName="seccion")
        capa_ahora = QHBoxLayout(ahora)
        capa_ahora.setContentsMargins(18, 14, 18, 14)
        textos_ahora = QVBoxLayout()
        textos_ahora.setSpacing(2)
        textos_ahora.addWidget(QLabel("AHORA MISMO", objectName="lema"))
        self.lbl_estado = QLabel("Detenido", objectName="estado_grande")
        textos_ahora.addWidget(self.lbl_estado)
        self.lbl_detalle = QLabel(objectName="tenue")
        textos_ahora.addWidget(self.lbl_detalle)
        capa_ahora.addLayout(textos_ahora, 1)
        self.fila_fases = QHBoxLayout()
        self.fila_fases.setSpacing(6)
        capa_ahora.addLayout(self.fila_fases)
        der.addWidget(ahora)

        rejilla = QGridLayout()
        rejilla.setSpacing(10)
        self.cifras = {}
        for i, (clave, titulo, ic) in enumerate(CIFRAS):
            marco, cifra = tarjeta(titulo, icono=ic)
            self.cifras[clave] = cifra
            rejilla.addWidget(marco, i // 3, i % 3)
        self.cifras["tiempo"].setText("0:00:00")
        der.addLayout(rejilla)

        cabecera = QHBoxLayout()
        icono_reg = QLabel()
        icono_reg.setPixmap(iconos.pixmap("registro", 18, tema.ACENTO))
        cabecera.addWidget(icono_reg)
        cabecera.addWidget(QLabel("Registro", objectName="titulo_seccion"))
        cabecera.addStretch()
        self.chk_debug = QCheckBox("Ver detalle técnico")
        cabecera.addWidget(self.chk_debug)
        b_limpiar = QPushButton("Limpiar", objectName="chico")
        b_limpiar.clicked.connect(lambda: self.registro.clear())
        cabecera.addWidget(b_limpiar)
        der.addLayout(cabecera)
        self.registro = QTextEdit(readOnly=True, objectName="registro")
        der.addWidget(self.registro, 1)

        fila.addLayout(izq, 4)
        fila.addLayout(der, 7)
        self.cuerpo.addLayout(fila, 1)

        self.combo.currentIndexChanged.connect(self._mostrar_opciones)
        self.b_iniciar.clicked.connect(self.iniciar)
        self.b_pausar.clicked.connect(self.pausar)
        self.b_detener.clicked.connect(self.detener)
        self.puente.log.connect(self.escribir)
        self.puente.estado.connect(self._estado)
        self.puente.stats.connect(self._stats)
        self.puente.terminado.connect(self._terminado)
        self.puente.tecla.connect(self._tecla)
        self.puente.orden.connect(self._orden)

        self.temporizador = QTimer(self, timeout=self._refrescar)
        self.temporizador.start(1000)
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
        self.nombre_modo.setText(cls.titulo_juego or cls.nombre)
        self.sub_modo.setText(" · ".join(x for x in (cls.subtitulo_juego, cls.duracion) if x))
        pix = iconos.redondo(IMAGENES / cls.imagen, 64, tema.ACENTO) if cls.imagen else None
        if pix:
            self.emblema.setPixmap(pix)
        else:
            self.emblema.clear()
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

        while self.fila_fases.count():
            w = self.fila_fases.takeAt(0).widget()
            if w:
                w.setParent(None)
        self.fases = [QLabel(f"Fase {n}", objectName="fase") for n in range(1, cls.fases + 1)]
        for etiqueta in self.fases:
            self.fila_fases.addWidget(etiqueta)
        self._pintar_estado()

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

    def preparar(self, id_modo: str, valores: dict):
        """Elegir modo y opciones desde fuera (p. ej. el boton Empezar de Inicio)."""
        indice = self.combo.findData(id_modo)
        if indice >= 0:
            self.combo.setCurrentIndex(indice)
        for clave, valor in valores.items():
            campo = self.campos.get(clave)
            if isinstance(campo, QSpinBox):
                campo.setValue(int(valor))
            elif isinstance(campo, QCheckBox):
                campo.setChecked(bool(valor))
            elif isinstance(campo, QComboBox):
                campo.setCurrentText(str(valor))
            elif campo is not None:
                campo.setText(str(valor))

    # ------------------------------------------------------------------ control
    def _problema(self, titulo: str, texto: str, remoto: bool):
        """Avisa de por que no se puede arrancar: en pantalla, o al movil si la orden vino de ahi."""
        if remoto:
            avisos.enviar(f"{titulo}: {texto}")
        else:
            QMessageBox.warning(self, titulo, texto)

    def iniciar(self, remoto: bool = False):
        # Antes de farmear, mirar si salio una version nueva (las revisiones automaticas son cada
        # 30 min y podria estar jugando con un guion viejo). Si no hay internet, sigue igual.
        est = self.app.estado_update
        if not self.app.update_bloqueante and (est is None or time.time() - est.revisado > 120):
            self.escribir("Buscando actualizaciones antes de empezar...", "debug")
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                estado = actualizador.revisar()
            finally:
                QApplication.restoreOverrideCursor()
            self.app._resultado_revision(estado)
        if self.app.update_bloqueante:
            self.app.mostrar_bloqueo()
            if remoto:
                avisos.enviar("Hay una actualizacion obligatoria: instalala en el PC antes de farmear.")
            return
        cls = self.modo_cls
        equipo = getattr(cls, "equipo", None)
        if equipo is not None:
            equipo.recargar()
            faltan = equipo.faltantes()
            if faltan and remoto:
                self._problema("Faltan capturas", "\n".join(f"• {d.descripcion}" for d in faltan), True)
                return
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
        if not self._preparar_ventana(remoto):
            return
        valores = self._valores()
        opciones = dict(config.obtener("opciones_modos") or {})
        opciones[cls.id] = valores
        config.guardar({"opciones_modos": opciones, "ultimo_modo": cls.id})
        for cifra in self.cifras.values():
            cifra.setText("0")
        self.cifras["tiempo"].setText("0:00:00")
        self.ultimas_stats = {}
        self.estado_bot = ""
        self.inicio = time.time()
        self.puente.iniciar(cls(valores))
        self._botones(True)
        self._pintar_estado()
        self.app.navegar("farmear")

    def _preparar_ventana(self, remoto: bool = False) -> bool:
        """Juego abierto, del tamano correcto y al frente. False si no se puede arrancar."""
        if not ventana.ventana_abierta():
            self._problema("Juego cerrado", f"No encuentro la ventana '{config.obtener('titulo_ventana')}'.", remoto)
            return False
        if not ventana.ajustar_tamano():
            if ventana.ultimo_error == ventana.AVISO_ADMIN:
                # Sin permisos tampoco funcionarian los clics: no tiene sentido arrancar.
                self._problema("Faltan permisos", ventana.AVISO_ADMIN, remoto)
                return False
            self.escribir(f"{ventana.ultimo_error} Puede fallar el reconocimiento.", "aviso")
        ventana.traer_al_frente()
        return True

    def ejecutar_herramienta(self, modo) -> bool:
        """Arranca un modo que no es de farmeo (la captura de heroes) y muestra su avance aqui."""
        if self.puente.corriendo or not self._preparar_ventana():
            return False
        self.modo_externo = type(modo)
        self.ultimas_stats = {}
        self.estado_bot = ""
        self.inicio = time.time()
        self.puente.iniciar(modo)
        self._botones(True)
        self._pintar_estado()
        self.app.navegar("farmear")
        return True

    def pausar(self):
        if not self.puente.corriendo:
            return
        if control.en_pausa:
            ventana.traer_al_frente()
            control.reanudar()
            self._texto_pausa(False)
        else:
            control.pausar()
            self._texto_pausa(True)
        self._pintar_estado()

    def _texto_pausa(self, en_pausa: bool):
        self.b_pausar.setText(" Reanudar" if en_pausa else " Pausar")
        self.b_pausar.setIcon(iconos.icono("jugar" if en_pausa else "pausa", tema.TEXTO))

    def detener(self):
        control.detener()
        self._texto_pausa(False)

    def _tecla(self, cual: str):
        if cual == "pausa":
            self.pausar()
        elif cual == "detener":
            self.detener()

    # ------------------------------------------------------------ ordenes del movil
    def _orden(self, orden: str):
        corriendo = self.puente.corriendo
        if orden == "ayuda":
            avisos.enviar(ordenes.texto_ayuda())
        elif orden == "estado":
            avisos.enviar(self._resumen())
        elif orden == "captura":
            try:
                imagen, _ = ventana.capturar()
            except Exception as error:
                avisos.enviar(f"No pude sacar la foto: {error}")
                return
            avisos.enviar(self._resumen(), imagen)
        elif orden == "iniciar":
            if corriendo:
                avisos.enviar("Ya esta en marcha. " + self._resumen())
                return
            self.escribir("Orden del movil: iniciar.", "info")
            self.iniciar(remoto=True)
            if self.puente.corriendo:
                avisos.enviar(f"Empiezo: {self.modo_cls.nombre}.")
        elif not corriendo:
            avisos.enviar("El bot no esta en marcha. Escribe 'iniciar' para empezar.")
        elif orden == "detener":
            self.escribir("Orden del movil: detener.", "aviso")
            self.detener()
            avisos.enviar("Detenido.")
        elif (orden == "pausar") != control.en_pausa:  # pausar sin pausa, o reanudar en pausa
            self.escribir(f"Orden del movil: {orden}.", "info")
            self.pausar()
            avisos.enviar("En pausa." if control.en_pausa else "Reanudado.")
        else:
            avisos.enviar("Ya estaba en pausa." if control.en_pausa else "No estaba en pausa.")

    def _resumen(self) -> str:
        """El estado en pocas lineas, para el movil."""
        self._pintar_estado()
        lineas = [f"{self.lbl_estado.text()} · {self.lbl_detalle.text()}"]
        if self.inicio:
            lineas.append(f"Tiempo: {formatear_tiempo(time.time() - self.inicio)}")
        s = self.ultimas_stats
        if s:
            lineas.append(" · ".join(f"{nombre}: {s[clave]:.0f}%" if clave == "tasa" else f"{nombre}: {s[clave]}"
                                     for clave, nombre, _ in CIFRAS if clave in s))
        return "\n".join(lineas)

    def _terminado(self):
        self._botones(False)
        self.inicio = None
        self.estado_bot = ""
        era_captura = getattr(self.modo_externo, "id", "") == "captura_heroes"
        self.modo_externo = None
        self._pintar_estado()
        if era_captura:  # al terminar, ensenar lo capturado
            self.app.navegar("capturados")

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
            "ratón a una esquina = freno de emergencia. Mientras farmea, no muevas el ratón."
        )

    # ------------------------------------------------------------ que esta haciendo
    def _estado(self, estado: str):
        if estado != self.estado_bot:
            self.estado_bot = estado
            self._pintar_estado()

    def _pintar_estado(self):
        corriendo = self.puente.corriendo
        cls = self.modo_externo if corriendo and self.modo_externo else self.modo_cls
        if not corriendo:
            texto, detalle = "Detenido", "Pulsa Iniciar (o Empezar en Inicio) para farmear."
        elif control.en_pausa:
            texto, detalle = "En pausa", "Pulsa Reanudar para seguir."
        else:
            texto = cls.nombres_estados.get(self.estado_bot) or self.estado_bot.replace("_", " ").capitalize() or "Arrancando"
            detalle = cls.titulo_juego or cls.nombre
        self.lbl_estado.setText(texto)
        self.lbl_detalle.setText(detalle)
        fase = int(self.ultimas_stats.get("fase") or 0) if corriendo else 0
        peleando = corriendo and self.estado_bot == "pelea"
        for n, etiqueta in enumerate(self.fases, start=1):
            if corriendo and self.estado_bot == "victoria":
                estado = "hecha"
            elif peleando and n < fase:
                estado = "hecha"
            elif peleando and n == fase:
                estado = "actual"
            else:
                estado = ""
            _repintar(etiqueta, "estado", estado)

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
        self._pintar_estado()

    def _refrescar(self):
        if self.inicio:
            self.cifras["tiempo"].setText(formatear_tiempo(time.time() - self.inicio))

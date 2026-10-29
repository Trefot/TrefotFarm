"""Pagina Farmear: el modo, los controles, que esta haciendo el bot, el botin que lleva, los mejores
equipos para ese modo, el registro y las opciones. Todo en una pantalla."""

import time

from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtGui import QPixmap, QTextCursor
from PyQt5.QtWidgets import (
    QApplication,
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
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
)

from lumen import actualizador, avisos, botin, config, informe, metas, ordenes, recompensas, ventana
from lumen.control import control
from lumen.gui import iconos, plan, resumen, tema
from lumen.gui.metas import FilaMateriales
from lumen.gui.arranque import EMBLEMA
from lumen.gui.comun import Pagina, formatear_tiempo
from lumen.gui.paginas.equipos import clave_de_equipos, tarjetas_equipos
from lumen.modos import MODOS
from lumen.modos.catalogo import CATALOGO, contenido_de, foto_de
from lumen.rutas import IMAGENES, LOGS

CIFRAS = [("victorias", "Victorias", "trofeo"), ("derrotas", "Derrotas", "derrota"), ("reinicios", "Reinicios", "reinicio"),
          ("tasa", "% de éxito", "tasa"), ("pociones", "Pociones", "pocion"), ("tiempo", "Tiempo", "reloj")]


def _repintar(widget, propiedad: str, valor):
    widget.setProperty(propiedad, valor)
    widget.style().unpolish(widget)
    widget.style().polish(widget)



def tareas_de_prueba() -> list[dict]:
    """Los modos de farmeo listos, en el orden del catalogo, con 1 victoria cada uno."""
    return [{"modo": d.id, "victorias": 1} for c in CATALOGO for d in c.destinos if d.id in MODOS]


class VentanaInforme(QDialog):
    """El informe de la prueba rapida, con un boton para copiarlo (y pegarlo a quien mantiene el bot)."""

    def __init__(self, padre, texto: str):
        super().__init__(padre)
        self.setWindowTitle("Informe de la prueba")
        self.resize(560, 420)
        capa = QVBoxLayout(self)
        capa.addWidget(QLabel("Prueba rápida terminada. También te llegó al móvil.", objectName="titulo_seccion"))
        caja = QTextEdit(readOnly=True, objectName="registro")
        caja.setPlainText(texto)
        capa.addWidget(caja, 1)
        fila = QHBoxLayout()
        fila.addStretch()
        b_copiar = QPushButton(" Copiar", objectName="primario")
        b_copiar.setIcon(iconos.icono("mdi6.content-copy", tema.SOBRE_ACENTO))
        b_copiar.clicked.connect(lambda: (QApplication.clipboard().setText(texto), b_copiar.setText(" Copiado")))
        fila.addWidget(b_copiar)
        b_cerrar = QPushButton("Cerrar")
        b_cerrar.clicked.connect(self.close)
        fila.addWidget(b_cerrar)
        capa.addLayout(fila)

class PaginaFarmear(Pagina):
    titulo = "Farmear"

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

        # ---- arriba: el modo con su foto, el estado en grande y las fases
        ahora = QFrame(objectName="seccion")
        capa_ahora = QHBoxLayout(ahora)
        capa_ahora.setContentsMargins(18, 14, 18, 14)
        capa_ahora.setSpacing(16)
        self.emblema = QLabel()
        self.emblema.setFixedSize(112, 112)
        capa_ahora.addWidget(self.emblema)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        self.nombre_modo = QLabel(objectName="titulo_tarjeta")
        self.sub_modo = QLabel(objectName="tenue")
        textos.addStretch()
        textos.addWidget(self.nombre_modo)
        textos.addWidget(self.sub_modo)
        self.fila_pisos = QHBoxLayout()  # Floor 1 -> 2 -> 3 en los modos que recorren pisos
        self.fila_pisos.setSpacing(4)
        textos.addLayout(self.fila_pisos)
        self.pisos: dict[int, QLabel] = {}
        self.combo = QComboBox()
        for modo in MODOS.values():
            self.combo.addItem(modo.nombre, modo.id)
        self.combo.setCurrentIndex(max(0, self.combo.findData(config.obtener("ultimo_modo"))))
        self.combo.setVisible(len(MODOS) > 1)
        self.combo.setMaximumWidth(340)
        textos.addWidget(self.combo)
        textos.addStretch()
        capa_ahora.addLayout(textos, 1)
        estado = QVBoxLayout()
        estado.setSpacing(6)
        estado.addStretch()
        self.lbl_estado = QLabel("Detenido", objectName="estado_grande", alignment=Qt.AlignRight)
        estado.addWidget(self.lbl_estado)
        self.lbl_detalle = QLabel(objectName="tenue", alignment=Qt.AlignRight)
        estado.addWidget(self.lbl_detalle)
        self.fila_fases = QHBoxLayout()
        self.fila_fases.setSpacing(6)
        self.fila_fases.addStretch()
        estado.addLayout(self.fila_fases)
        # Controles en la cabecera, bajo el estado: Iniciar, Pausar y Detener
        botones = QHBoxLayout()
        botones.setSpacing(8)
        botones.addStretch()
        self.b_iniciar = QToolButton(objectName="iniciar", text="Iniciar")
        self.b_pausar = QToolButton(objectName="pausar", text="Pausar")
        self.b_detener = QToolButton(objectName="detener", text="Detener")
        for b, ic in ((self.b_iniciar, "jugar"), (self.b_pausar, "pausa"), (self.b_detener, "detener")):
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setIcon(iconos.icono(ic, tema.TEXTO))
            b.setIconSize(QSize(22, 22))
            b.setFixedSize(84, 60)
            b.setCursor(Qt.PointingHandCursor)
            botones.addWidget(b)
        estado.addLayout(botones)
        self.ayuda_teclas = QLabel(objectName="tenue", alignment=Qt.AlignRight)
        estado.addWidget(self.ayuda_teclas)
        estado.addStretch()
        capa_ahora.addLayout(estado)
        self.cuerpo.addWidget(ahora)

        # ---- cifras en una fila
        fila_cifras = QHBoxLayout()
        fila_cifras.setSpacing(10)
        self.cifras = {}
        for clave, titulo, ic in CIFRAS:
            marco = QFrame(objectName="cifra_mini")
            marco.setToolTip(titulo)
            capa = QVBoxLayout(marco)
            capa.setContentsMargins(8, 8, 8, 6)
            capa.setSpacing(0)
            arriba = QHBoxLayout()
            arriba.addStretch()
            dibujo = QLabel()
            dibujo.setPixmap(iconos.pixmap(ic, 20, tema.ACENTO))
            arriba.addWidget(dibujo)
            cifra = QLabel("0", objectName="cifra")
            arriba.addWidget(cifra)
            arriba.addStretch()
            capa.addLayout(arriba)
            capa.addWidget(QLabel(titulo, objectName="tenue", alignment=Qt.AlignCenter))
            self.cifras[clave] = cifra
            fila_cifras.addWidget(marco)
        self.cifras["tiempo"].setText("0:00:00")
        self.cuerpo.addLayout(fila_cifras)

        # ---- botin: lo que se lleva conseguido (esta sesion, o hoy en este modo si esta parado)
        caja_botin = QFrame(objectName="seccion")
        capa_botin = QHBoxLayout(caja_botin)
        capa_botin.setContentsMargins(14, 8, 8, 8)
        capa_botin.setSpacing(12)
        textos_botin = QVBoxLayout()
        textos_botin.setSpacing(0)
        self.lbl_botin = QLabel(objectName="titulo_seccion")
        self.lbl_oro = QLabel(objectName="tenue")
        textos_botin.addStretch()
        textos_botin.addWidget(self.lbl_botin)
        textos_botin.addWidget(self.lbl_oro)
        textos_botin.addStretch()
        capa_botin.addLayout(textos_botin)
        self.fila_botin = QHBoxLayout()
        self.fila_botin.setSpacing(8)
        contenedor = QFrame(objectName="contenido_desplazable")
        contenedor.setLayout(self.fila_botin)
        desliza = QScrollArea(objectName="area_pagina", widgetResizable=True, frameShape=QFrame.NoFrame)
        desliza.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        desliza.setWidget(contenedor)
        desliza.setFixedHeight(78)
        capa_botin.addWidget(desliza, 1)
        # A la derecha: "Metas", los materiales de este modo (al tocar uno, su meta en Inicio)
        self.raya_premios = QFrame(frameShape=QFrame.VLine, objectName="raya")
        capa_botin.addWidget(self.raya_premios)
        self.fila_metas = FilaMateriales(34, "premio_mini", centrar=False, titulo_arriba=True)
        self.fila_metas.tocado.connect(lambda o: self.app.paginas["inicio"].abrir_meta(o, self.modo_cls.id))
        capa_botin.addWidget(self.fila_metas)
        self._firma_metas = None
        self.cuerpo.addWidget(caja_botin)
        self._fotos_vistas = None

        # ---- abajo: registro u opciones, una cosa a la vez
        cabecera = QHBoxLayout()
        self.grupo_vista = QButtonGroup(self, exclusive=True)
        self.pila_vista = QStackedWidget()
        self.registro = QTextEdit(readOnly=True, objectName="registro")
        panel_opciones = QFrame(objectName="seccion")
        capa_op = QVBoxLayout(panel_opciones)
        self.descripcion = QLabel(wordWrap=True, objectName="tenue")
        capa_op.addWidget(self.descripcion)
        self.form = QFormLayout()
        capa_op.addLayout(self.form)
        capa_op.addStretch()
        # Los mejores equipos para el modo elegido (los mismos que la pagina Equipos, hasta 5), a la derecha
        contenedor_eq = QFrame(objectName="contenido_desplazable")
        self.lista_equipos = QVBoxLayout(contenedor_eq)
        self.lista_equipos.setContentsMargins(0, 0, 6, 0)
        panel_equipos = QScrollArea(objectName="area_pagina", widgetResizable=True, frameShape=QFrame.NoFrame)
        panel_equipos.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        panel_equipos.setWidget(contenedor_eq)
        self.panel_plan = plan.PanelPlan()
        self.panel_plan.iniciar.connect(self.iniciar_plan)
        self.panel_plan.saltar.connect(self.saltar_tarea)
        self.panel_plan.probar.connect(self.iniciar_prueba)
        self.plan_paso: int | None = None  # tarea del plan en curso (None = no hay plan en marcha)
        self.plan_resumenes: list[dict] = []  # lo conseguido en cada tarea: un solo resumen al acabar el plan
        self.plan_sin_estamina = False
        self.plan_saltar = False  # se detuvo la tarea en curso para pasar a la siguiente (no el plan)
        self.plan_tareas: list[dict] = []  # las tareas del plan en marcha (el guardado o el de la prueba)
        self.plan_prueba = False  # el plan en marcha es la prueba rapida: al final, un informe
        self.plan_resultados: list[dict] = []  # como acabo cada tarea (para el informe)
        self.ultimo_problema = ""  # por que no pudo empezar la ultima vez
        self.parar_en_meta = False  # parar (o pasar a la siguiente tarea del plan) al cumplir las metas
        self.metas_objetivo: list[str] = []  # las metas que llena el modo en marcha
        self._ultima_revision_metas = 0.0
        for i, (texto, ic, vista) in enumerate((("Registro", "registro", self.registro), ("Plan", "mdi6.format-list-checks", self.panel_plan),
                                               ("Opciones", "ajustes", panel_opciones))):
            b = QPushButton(" " + texto, objectName="chip", checkable=True, checked=i == 0)
            b.setIcon(iconos.icono(ic, tema.TENUE, tema.SOBRE_ACENTO))
            b.clicked.connect(lambda _, n=i: self._ver_vista(n))
            self.grupo_vista.addButton(b)
            cabecera.addWidget(b)
            self.pila_vista.addWidget(vista)
        cabecera.addStretch()
        self.chk_debug = QCheckBox("Detalle técnico")
        cabecera.addWidget(self.chk_debug)
        b_limpiar = QPushButton(objectName="chico")
        b_limpiar.setIcon(iconos.icono("mdi6.broom", tema.TEXTO))
        b_limpiar.setToolTip("Limpiar el registro")
        b_limpiar.clicked.connect(lambda: self.registro.clear())
        cabecera.addWidget(b_limpiar)
        self.solo_registro = (self.chk_debug, b_limpiar)  # solo sirven con el registro a la vista
        izquierda = QVBoxLayout()
        izquierda.addLayout(cabecera)
        izquierda.addWidget(self.pila_vista, 1)
        derecha = QVBoxLayout()
        titulo_eq = QHBoxLayout()
        icono_eq = QLabel()
        icono_eq.setPixmap(iconos.pixmap("equipos", 18, tema.ACENTO))
        titulo_eq.addWidget(icono_eq)
        titulo_eq.addWidget(QLabel("Mejores equipos", objectName="titulo_seccion"))
        titulo_eq.addStretch()
        derecha.addLayout(titulo_eq)
        derecha.addWidget(panel_equipos, 1)
        abajo = QHBoxLayout()
        abajo.setSpacing(14)
        abajo.addLayout(izquierda, 4)
        abajo.addLayout(derecha, 5)
        self.cuerpo.addLayout(abajo, 1)

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

    def _ver_vista(self, n: int):
        """Registro (0), Plan (1) u Opciones (2) abajo a la izquierda."""
        self.pila_vista.setCurrentIndex(n)
        self.grupo_vista.buttons()[n].setChecked(True)
        for w in self.solo_registro:
            w.setVisible(n == 0)

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
        self.nombre_modo.setToolTip(cls.descripcion)
        foto = foto_de(cls.id) or (IMAGENES / cls.imagen if cls.imagen else None)  # la del catalogo (assets/modos) o la del modo
        pix = iconos.redondo(foto, 112, tema.ACENTO) if foto else None
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

        while self.fila_pisos.count():
            w = self.fila_pisos.takeAt(0).widget()
            if w:
                w.setParent(None)
        self.pisos = {}
        for i, n in enumerate(getattr(cls, "ciclo_pisos", ())):
            if i:
                flecha = QLabel()
                flecha.setPixmap(iconos.pixmap("mdi6.chevron-right", 16, tema.TENUE))
                self.fila_pisos.addWidget(flecha)
            self.pisos[n] = QLabel(f"Floor {n}", objectName="piso", alignment=Qt.AlignCenter)
            self.fila_pisos.addWidget(self.pisos[n])
        if self.pisos:
            self.lbl_vuelta = QLabel(objectName="tenue")
            self.fila_pisos.addSpacing(8)
            self.fila_pisos.addWidget(self.lbl_vuelta)
        self.fila_pisos.addStretch()
        self._pintar_equipos()
        self._pintar_botin()
        self._pintar_premios()
        while self.fila_fases.count():
            w = self.fila_fases.takeAt(0).widget()
            if w:
                w.setParent(None)
        self.fases = [QLabel(str(n), objectName="fase", alignment=Qt.AlignCenter, toolTip=f"Fase {n}")
                      for n in range(1, cls.fases + 1)]
        self.fila_fases.addStretch()  # pegadas a la derecha, bajo el estado
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
        """Avisa de por que no se puede arrancar: en pantalla, o al movil si la orden vino de ahi.
        En la prueba rapida solo se apunta (sale en el informe)."""
        self.ultimo_problema = f"{titulo}: {texto.splitlines()[0] if texto else ''}".rstrip(": ")
        if self.plan_prueba:
            self.escribir(self.ultimo_problema, "aviso")
        elif remoto:
            avisos.enviar(f"{titulo}: {texto}")
        else:
            QMessageBox.warning(self, titulo, texto)

    def iniciar(self, remoto: bool = False, meta: bool = False):
        """``meta``: parar al completar las metas que llena este modo (el chip "Meta" de Inicio)."""
        self.parar_en_meta, self.metas_objetivo = False, []
        if meta:
            self.metas_objetivo = [m.objeto for m in metas.del_destino(self.modo_cls.id, metas.cargar(fresco=True))]
            self.parar_en_meta = bool(self.metas_objetivo)
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
            if faltan and (remoto or self.plan_prueba):
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
        if self.plan_paso is None:
            # Lo que elige el jugador se recuerda; lo de un plan o de la prueba rapida no: la prueba pone 1
            # victoria a cada modo y luego Inicio mostraba "1" en todos (el Floor 1-3 paraba tras un piso).
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
        self.b_pausar.setText("Reanudar" if en_pausa else "Pausar")
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
        elif orden == "plan":
            if corriendo:
                avisos.enviar("Ya está en marcha. " + self._resumen())
                return
            self.escribir("Orden del movil: plan del día.", "info")
            self.iniciar_plan(remoto=True)
            if self.puente.corriendo:
                avisos.enviar(f"Empiezo el plan del día: {len(plan.cargar())} tareas.")
        elif orden == "prueba":
            if corriendo:
                avisos.enviar("Ya está en marcha. " + self._resumen())
                return
            self.escribir("Orden del movil: prueba rápida.", "info")
            self.iniciar_prueba(remoto=True)
            if self.puente.corriendo:
                avisos.enviar(f"Empiezo la prueba rápida: {len(self.plan_tareas)} modos, 1 victoria de cada uno.")
        elif orden == "diario":
            from lumen.ia import diario

            from lumen.ia import aprendizaje

            texto = diario.texto(self.modo_cls.id, self.modo_cls.nombre)
            if any(p.get("config") for p in diario.leer(self.modo_cls.id, 1000)):
                texto += "\n" + aprendizaje.texto(diario.leer(self.modo_cls.id, 1000))
            avisos.enviar(texto)
        elif orden == "plan ver":
            avisos.enviar(self._texto_plan())
        elif orden == "saltar":
            if self.plan_paso is None or not corriendo:
                avisos.enviar("No hay ningún plan en marcha.")
                return
            self.escribir(f"Orden del movil: saltar la tarea {self.plan_paso + 1}.", "aviso")
            self.saltar_tarea()
            avisos.enviar(f"Dejo la tarea {self.plan_paso + 1} y paso a la siguiente.")
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
        segundos = time.time() - self.inicio if self.inicio else 0
        if not self.modo_externo:  # solo las sesiones de farmeo, no las herramientas del admin
            self._mostrar_resumen()
        self._pintar_botin()
        self._botones(False)
        self.inicio = None
        self.estado_bot = ""
        if self.plan_paso is not None:
            if self.ultimas_stats.get("motivo_fin") == "sin_estamina":
                self.plan_sin_estamina = True
            saltada, self.plan_saltar = self.plan_saltar, False
            self._apuntar_resultado(segundos, saltada)
            if self.app.update_bloqueante or (not saltada and (control.detenido or control.parar_en_zona_segura)):
                self.escribir("Plan del día detenido.", "aviso")
                self._fin_plan()
            else:  # unos segundos para que el juego vuelva a un menu antes de la siguiente tarea
                QTimer.singleShot(4000, lambda: self._siguiente_tarea(remoto=True))
        herramienta = getattr(self.modo_externo, "id", "")
        self.modo_externo = None
        self._pintar_estado()
        if herramienta == "captura_heroes":  # al terminar, ensenar lo capturado
            self.app.navegar("capturados")
        elif herramienta == "aprender":  # y lo medido con las peleas que jugo el admin
            self.app.navegar("equipos")
        elif herramienta == "captura_objetos":  # y la galeria de objetos
            self.app.navegar("recompensas")

    # ------------------------------------------------------------ plan del dia
    def iniciar_plan(self, remoto: bool = False, tareas: list[dict] | None = None, prueba: bool = False):
        """Empieza el plan del dia (o las ``tareas`` dadas) por la primera tarea."""
        if self.puente.corriendo:
            return
        tareas = tareas if tareas is not None else plan.cargar()
        if not tareas:
            self._problema("Plan del día", "El plan no tiene tareas.", remoto)
            return
        self.escribir("Empieza la prueba rápida." if prueba else "Empieza el plan del día.", "ok")
        self.plan_tareas = tareas
        self.plan_prueba = prueba
        self.plan_resultados = []
        self.plan_paso = -1
        self.plan_resumenes = []
        self.plan_sin_estamina = False
        self._siguiente_tarea(remoto)

    def iniciar_prueba(self, remoto: bool = False):
        """Prueba rapida: 1 victoria de cada modo listo, una tras otra, y un informe al final."""
        if self.puente.corriendo:
            return
        tareas = tareas_de_prueba()
        if not ventana.ventana_abierta():
            self._problema("Juego cerrado", "Abre el juego y llega a la Tavern antes de la prueba.", remoto)
            return
        if not remoto and QMessageBox.question(
                self, "Prueba rápida",
                f"Juego 1 victoria de cada modo listo ({len(tareas)}), uno tras otro, y al final te doy un informe "
                "con lo que funcionó y lo que no.\n\nDeja el juego en la Tavern con el equipo puesto. "
                "F10 para pararla.\n\n¿Empezar?") != QMessageBox.Yes:
            return
        self.iniciar_plan(remoto, tareas, prueba=True)

    def _apuntar_resultado(self, segundos: float, saltada: bool):
        """Como acabo la tarea en curso del plan (para el informe de la prueba)."""
        if not 0 <= self.plan_paso < len(self.plan_tareas):
            return
        v = int(self.ultimas_stats.get("victorias", 0) or 0)
        error = self.puente.ultimo_error
        if error:
            resultado, motivo = "fallo", f"ERROR: {error}"
        elif saltada:
            resultado, motivo = "saltada", "saltada a mano"
        elif v >= 1:
            resultado, motivo = "ok", ""
        elif control.detenido:
            resultado, motivo = "detenida", "detenida a mano"
        else:
            fin = self.ultimas_stats.get("motivo_fin", "")
            resultado, motivo = "sin_victoria", "sin estamina" if fin == "sin_estamina" else (fin or "acabó sin ganar")
        self._resultado(self.plan_paso, resultado, motivo, v, segundos)

    def _resultado(self, i: int, resultado: str, motivo: str = "", victorias: int = 0, segundos: float = 0):
        self.plan_resultados.append({"nombre": MODOS[self.plan_tareas[i]["modo"]].nombre, "resultado": resultado,
                                     "motivo": motivo, "victorias": victorias, "segundos": segundos})

    def saltar_tarea(self):
        """Detiene la tarea en curso; el plan sigue con la siguiente."""
        if self.plan_paso is not None and self.puente.corriendo:
            self.plan_saltar = True
            self.detener()

    def _texto_plan(self) -> str:
        """Las tareas del plan para el movil: ✓ hecha, ▶ en curso."""
        tareas = self.plan_tareas if self.plan_paso is not None else plan.cargar()
        if not tareas:
            return "El plan no tiene tareas. Añádelas en Farmear → Plan."
        lineas = [f"Plan del día · tarea {self.plan_paso + 1} de {len(tareas)}" if self.plan_paso is not None
                  else f"Plan del día · {len(tareas)} tareas (no está en marcha)"]
        for i, t in enumerate(tareas):
            marca = "▶" if i == self.plan_paso else "✓" if self.plan_paso is not None and i < self.plan_paso else "•"
            lineas.append(f"{marca} {i + 1}. {MODOS[t['modo']].nombre} · {plan.texto_victorias(t['victorias'])}")
        return "\n".join(lineas)

    def _siguiente_tarea(self, remoto: bool = True):
        """Arranca la siguiente tarea del plan; si una no puede empezar, prueba con la siguiente."""
        if self.plan_paso is None or self.puente.corriendo:
            return
        tareas = self.plan_tareas
        for i in range(self.plan_paso + 1, len(tareas)):
            t = tareas[i]
            self.plan_paso = i
            if self.plan_sin_estamina and any(op.clave == "pociones" for op in MODOS[t["modo"]].opciones):
                self.escribir(f"Plan: salto la tarea {i + 1} ({MODOS[t['modo']].nombre}): no queda estamina.", "aviso")
                self._resultado(i, "saltada", "sin estamina")
                continue
            if not self.plan_prueba:
                self.panel_plan.marcar(i)
            hasta_meta = int(t["victorias"]) == 0
            if hasta_meta and not metas.del_destino(t["modo"], metas.cargar(fresco=True)):
                # Sin metas pendientes que de este modo, "hasta la meta" seria farmear sin fin: se salta.
                self.escribir(f"Plan: salto la tarea {i + 1} ({MODOS[t['modo']].nombre}): no le queda ninguna meta.", "aviso")
                self._resultado(i, "saltada", "sus metas ya están completas")
                continue
            self.escribir(f"Plan: tarea {i + 1} de {len(tareas)} · {MODOS[t['modo']].nombre} · "
                          f"{plan.texto_victorias(t['victorias'])}.", "ok")
            self.preparar(t["modo"], {"victorias": int(t["victorias"])})
            self.ultimo_problema = ""
            self.iniciar(remoto=remoto, meta=hasta_meta)
            if self.puente.corriendo:
                return
            self.escribir(f"La tarea {i + 1} no pudo empezar; paso a la siguiente.", "aviso")
            self._resultado(i, "no_empezo", f"no empezó: {self.ultimo_problema}" if self.ultimo_problema else "no empezó")
        self.escribir("Prueba rápida terminada." if self.plan_prueba else "Plan del día terminado.", "ok")
        self._fin_plan()

    def _fin_plan(self):
        """Cierra el plan y muestra un solo resumen con lo de todas sus tareas (tambien al movil)."""
        self.plan_paso = None
        self.panel_plan.marcar(None)
        if self.plan_prueba:
            self.plan_prueba = False
            self.plan_resumenes = []
            self._informe_prueba(informe.texto_prueba(self.plan_resultados))
            return
        if self.plan_resumenes:
            n = len(self.plan_resumenes)
            nombre = f"Plan del día ({n} tarea{'s' if n != 1 else ''})"
            d = resumen.juntar(self.plan_resumenes)
            resumen.enviar_al_movil(nombre, d)
            self._tarjeta_resumen = resumen.TarjetaResumen(self, nombre, EMBLEMA, d)
            self._tarjeta_resumen.show()
        else:
            avisos.enviar("Lumen Farm: plan del día terminado.")
        self.plan_resumenes = []

    def _informe_prueba(self, texto: str):
        """El informe de la prueba: en una ventana para copiarlo, al movil y en logs/."""
        try:
            (LOGS / f"prueba_{time.strftime('%Y%m%d_%H%M%S')}.txt").write_text(texto, encoding="utf-8")
        except OSError:
            pass
        avisos.enviar(texto)
        self.escribir(texto, "info")
        self._ventana_informe = VentanaInforme(self, texto)
        self._ventana_informe.show()

    def _mostrar_resumen(self):
        """Tarjeta con lo conseguido en la sesion que acaba de terminar, y lo mismo al movil."""
        segundos = time.time() - self.inicio if self.inicio else 0
        if segundos < resumen.MINIMO_S:
            return
        sesion = self.ultimas_stats.get("inicio")
        registros = [r for r in recompensas.leer() if sesion and abs(float(r.get("sesion") or 0) - float(sesion)) < 1]
        cls = self.modo_cls
        d = resumen.datos(self.ultimas_stats, segundos, registros)
        if self.plan_paso is not None:  # en un plan, un solo resumen al final (ver _fin_plan)
            self.plan_resumenes.append(d)
            return
        resumen.enviar_al_movil(cls.nombre, d)
        self._tarjeta_resumen = resumen.TarjetaResumen(self, cls.nombre, foto_de(cls.id), d)
        self._tarjeta_resumen.show()  # sin bloquear: el programa sigue aunque nadie la cierre

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
            "ratón a una esquina = freno")
        self.ayuda_teclas.setToolTip("Mientras farmea, el bot usa tu ratón: no lo muevas.")

    # ------------------------------------------------------------ que esta haciendo
    def _estado(self, estado: str):
        if estado != self.estado_bot:
            self.estado_bot = estado
            self._pintar_estado()

    def _pintar_estado(self):
        corriendo = self.puente.corriendo
        cls = self.modo_externo if corriendo and self.modo_externo else self.modo_cls
        if not corriendo:
            texto, detalle = "Detenido", ""
        elif control.en_pausa:
            texto, detalle = "En pausa", ""
        else:
            texto = cls.nombres_estados.get(self.estado_bot) or self.estado_bot.replace("_", " ").capitalize() or "Arrancando"
            detalle = "" if cls is self.modo_cls else (cls.titulo_juego or cls.nombre)  # el modo elegido ya sale a la izquierda
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
        # Floor 1 -> 2 -> 3: el actual en dorado y los ya ganados en esta vuelta en verde
        piso = int(self.ultimas_stats.get("piso") or 0) if corriendo else 0
        for n, etiqueta in self.pisos.items():
            _repintar(etiqueta, "estado", "actual" if n == piso else "hecha" if piso and n < piso else "")
        if self.pisos:
            vuelta = int(self.ultimas_stats.get("vuelta") or 0) if corriendo else 0
            self.lbl_vuelta.setText(f"vuelta {vuelta}" if vuelta else "")

    # ------------------------------------------------------- equipos y botin
    # ------------------------------------------------------------ metas de material
    def repintar_metas(self):
        self._pintar_premios()

    def _revisar_metas(self):
        """Con el bot en marcha: avance de las metas y, si se pidio, parar al cumplirlas."""
        todas = metas.cargar()
        if tuple((m.objeto, m.actual, m.quiero) for m in todas) != self._firma_metas:
            self._pintar_premios()  # avanzo una meta: su barrita en la fila "Metas"
        if not self.parar_en_meta:
            return
        pendientes = [m for m in todas if m.objeto in self.metas_objetivo and not m.completa]
        if pendientes:
            return
        nombres = ", ".join(m.nombre for m in todas if m.objeto in self.metas_objetivo)
        self.parar_en_meta = False
        self.escribir(f"Meta cumplida: {nombres}.", "ok")
        avisos.enviar(f"Lumen Farm: meta cumplida ({nombres}).")
        if self.plan_paso is not None:
            self.saltar_tarea()  # en un plan, sigue con la siguiente tarea
        else:
            self.detener()

    def ver_equipos(self):
        """Abre Farmear, donde estan los mejores equipos (p. ej. desde el icono Equipo de Inicio)."""
        self.app.navegar("farmear")

    def _pintar_equipos(self):
        while self.lista_equipos.count():
            w = self.lista_equipos.takeAt(0).widget()
            if w:
                w.setParent(None)
        tarjetas = tarjetas_equipos(clave_de_equipos(self.modo_cls.id), compacto=True)[:5]
        if not tarjetas:  # p. ej. Hraesvelgr solo tiene equipos para el Floor 4: tambien sirven en el 1-3
            contenido = contenido_de(self.modo_cls.id)
            for destino in (contenido.destinos if contenido else ()):
                tarjetas = tarjetas_equipos(destino.id, compacto=True)[:5]
                if tarjetas:
                    self.lista_equipos.addWidget(QLabel(f"Del {destino.nombre}: también sirven aquí.", objectName="tenue"))
                    break
        for t in tarjetas:
            self.lista_equipos.addWidget(t)
        if not tarjetas:
            self.lista_equipos.addWidget(QLabel("Todavía no hay equipos recomendados para este modo.", objectName="tenue"))
        self.lista_equipos.addStretch(1)

    def _pintar_premios(self):
        todas = metas.cargar()
        self._firma_metas = tuple((m.objeto, m.actual, m.quiero) for m in todas)
        self.fila_metas.pintar(self.modo_cls.id, todas)
        self.raya_premios.setVisible(bool(self.fila_metas.objetos))

    def _pintar_botin(self):
        """Los objetos y el oro de la sesion en curso (o de hoy en este modo, con el bot parado)."""
        while self.fila_botin.count():
            w = self.fila_botin.takeAt(0).widget()
            if w:
                w.setParent(None)
        registros = recompensas.leer()
        sesion = self.ultimas_stats.get("inicio") if self.puente.corriendo else None
        if sesion:
            elegidos = [r for r in registros if abs(float(r.get("sesion") or 0) - float(sesion)) < 1]
            self.lbl_botin.setText("Botín de esta sesión")
        else:
            inicio_hoy = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
            elegidos = [r for r in registros if r.get("modo") == self.modo_cls.id and r.get("fecha", 0) >= inicio_hoy]
            self.lbl_botin.setText("Botín de hoy")
        oro = sum(int(r.get("oro") or 0) for r in elegidos)
        victorias = len(elegidos)
        self.lbl_oro.setText(f"{oro:,} de oro · {victorias} victoria{'s' if victorias != 1 else ''}".replace(",", "."))
        catalogo = botin.cargar_catalogo()
        totales = recompensas.totales_objetos(elegidos)
        for oid, cantidad in list(totales.items())[:40]:
            casilla = QFrame(objectName="objeto_mini")
            capa = QVBoxLayout(casilla)
            capa.setContentsMargins(4, 4, 4, 2)
            capa.setSpacing(0)
            dibujo = QLabel(alignment=Qt.AlignCenter)
            pix = QPixmap(str(botin.ruta_icono(oid)))
            if not pix.isNull():
                dibujo.setPixmap(pix.scaled(44, 38, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            capa.addWidget(dibujo)
            capa.addWidget(QLabel(f"×{cantidad:,}".replace(",", "."), objectName="cantidad_mini", alignment=Qt.AlignCenter))
            casilla.setToolTip(botin.nombre(oid, catalogo))
            self.fila_botin.addWidget(casilla)
        if not totales:
            self.fila_botin.addWidget(QLabel("Aún nada: cada victoria suma aquí lo que consigas.", objectName="tenue"))
        self.fila_botin.addStretch(1)

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
        if s.get("fotos_recompensas") != self._fotos_vistas:  # una victoria nueva con su botin
            self._fotos_vistas = s.get("fotos_recompensas")
            self._pintar_botin()

    def _refrescar(self):
        if self.puente.corriendo and time.time() - self._ultima_revision_metas > 5:
            self._ultima_revision_metas = time.time()
            self._revisar_metas()
        if self.inicio:
            self.cifras["tiempo"].setText(formatear_tiempo(time.time() - self.inicio))

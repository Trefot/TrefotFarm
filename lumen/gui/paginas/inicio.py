"""Pagina Inicio: cuatro comprobaciones en iconos, la rueda para elegir que farmear y Empezar."""

import time

from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QToolButton,
)

from lumen import config, historial, ventana
from lumen import personajes as P
from lumen.actualizador import version_local
from lumen.control import control
from lumen.gui import iconos, tema
from lumen.gui.comun import Pagina, formatear_tiempo
from lumen.gui.rueda import Rueda
from lumen.modos import MODOS
from lumen.modos.catalogo import CATALOGO, contenido_de

OPCIONES_VICTORIAS = [("1", 1), ("5", 5), ("10", 10), ("25", 25), ("∞", 0)]


class Paso(QToolButton):
    """Una comprobacion de 'antes de empezar': icono redondo y una o dos palabras debajo.

    El detalle sale al pasar el raton; el clic lleva a arreglarlo.
    """

    def __init__(self, icono: str, titulo: str, accion):
        super().__init__(objectName="paso")
        self.icono_nombre = icono
        self.titulo = titulo
        self.setCursor(Qt.PointingHandCursor)
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setIconSize(QSize(28, 28))
        self.setMinimumSize(118, 74)
        self.clicked.connect(accion)
        self.listo = False

    def poner(self, estado: str, texto: str, detalle: str):
        """estado: "ok" | "falta" | "nada" (no aplica al modo elegido)."""
        self.listo = estado != "falta"
        color = {"ok": tema.OK, "falta": tema.AVISO}.get(estado, tema.TENUE)
        self.setIcon(iconos.icono(self.icono_nombre, color))
        self.setText(f"{self.titulo}\n{texto}")
        self.setToolTip(detalle)
        self.setProperty("estado", estado)
        self.style().unpolish(self)
        self.style().polish(self)


class PaginaInicio(Pagina):
    desplazable = True
    titulo = "Inicio"

    def __init__(self, app):
        super().__init__()
        self.app = app
        guardado = config.obtener("ultimo_destino") or config.obtener("ultimo_modo")
        self.contenido = contenido_de(guardado) or CATALOGO[0]
        self.modo_id = guardado if contenido_de(guardado) else self.contenido.destinos[-1].id

        # ---- version (arriba a la derecha)
        self.lbl_version = QLabel(objectName="tenue")
        self.acciones.addWidget(self.lbl_version)
        self.b_buscar = QPushButton(objectName="chico")
        self.b_buscar.setIcon(iconos.icono("buscar", tema.TEXTO))
        self.b_buscar.setToolTip("Buscar actualizaciones")
        self.b_buscar.clicked.connect(lambda: app.buscar_updates(manual=True))
        self.b_actualizar = QPushButton(" Actualizar", objectName="primario")
        self.b_actualizar.setIcon(iconos.icono("actualizar", tema.SOBRE_ACENTO))
        self.b_actualizar.clicked.connect(app.accion_actualizar)
        self.acciones.addWidget(self.b_buscar)
        self.acciones.addWidget(self.b_actualizar)

        # ---- 1. Antes de empezar: cuatro iconos
        fila_pasos = QHBoxLayout()
        fila_pasos.setSpacing(10)
        fila_pasos.addStretch()
        self.pasos = {
            "juego": Paso("juego", "Juego", self._ayuda_juego),
            "ventana": Paso("ventana", "Ventana", self._ajustar),
            "equipo": Paso("equipo", "Equipo", lambda: app.navegar("equipos")),
            "cartas": Paso("cartas", "Cartas", lambda: app.navegar("personajes")),
        }
        for paso in self.pasos.values():
            fila_pasos.addWidget(paso)
        fila_pasos.addStretch()
        self.cuerpo.addLayout(fila_pasos)

        # ---- 2. La rueda
        listos = {c.id for c in CATALOGO if any(d.id in MODOS for d in c.destinos)}
        self.rueda = Rueda(CATALOGO, listos, CATALOGO.index(self.contenido))
        self.rueda.cambiado.connect(self._girada)
        self.cuerpo.addWidget(self.rueda)
        self.lbl_nombre = QLabel(objectName="nombre_rueda", alignment=Qt.AlignCenter)
        self.lbl_descripcion = QLabel(objectName="tenue", alignment=Qt.AlignCenter)
        self.cuerpo.addWidget(self.lbl_nombre)
        self.cuerpo.addWidget(self.lbl_descripcion)
        self.fila_destinos = QHBoxLayout()
        self.fila_destinos.setSpacing(8)
        self.grupo_destinos = QButtonGroup(self, exclusive=True)
        self.grupo_destinos.buttonClicked.connect(lambda b: self._elegir_destino(b.property("destino")))
        self.cuerpo.addLayout(self.fila_destinos)
        self.fila_equipo = QHBoxLayout()
        self.fila_equipo.setSpacing(6)
        self.cuerpo.addLayout(self.fila_equipo)
        self.lbl_estado = QLabel(alignment=Qt.AlignCenter)
        self.cuerpo.addWidget(self.lbl_estado)
        self.cuerpo.addStretch()

        # ---- 3. Victorias, pociones y Empezar
        barra_inicio = QFrame(objectName="seccion")
        fila = QHBoxLayout(barra_inicio)
        fila.setContentsMargins(14, 10, 10, 10)
        trofeo = QLabel()
        trofeo.setPixmap(iconos.pixmap("trofeo", 22, tema.ACENTO))
        trofeo.setToolTip("Cuántas victorias antes de parar")
        fila.addWidget(trofeo)
        self.grupo_victorias = QButtonGroup(self, exclusive=True)
        for texto, valor in OPCIONES_VICTORIAS:
            b = QPushButton(texto, objectName="chip", checkable=True)
            b.setMinimumWidth(46)
            b.setProperty("valor", valor)
            b.setToolTip("Sin límite" if not valor else f"Parar tras {valor} victorias")
            self.grupo_victorias.addButton(b)
            fila.addWidget(b)
        fila.addSpacing(14)
        self.chk_pociones = QCheckBox("Pociones")
        self.chk_pociones.setIcon(iconos.icono("pocion", tema.TENUE))
        self.chk_pociones.setToolTip("Usar pociones de stamina si se acaba")
        fila.addWidget(self.chk_pociones)
        fila.addStretch()
        self.vivo = QLabel(objectName="tenue")
        fila.addWidget(self.vivo)
        self.b_empezar = QPushButton("  Empezar", objectName="empezar")
        self.b_empezar.setIconSize(QSize(22, 22))
        self.b_empezar.setMinimumSize(190, 52)
        self.b_empezar.clicked.connect(self._empezar_o_detener)
        fila.addWidget(self.b_empezar)
        self.cuerpo.addWidget(barra_inicio)

        # ---- 4. Hoy
        self.lbl_hoy = QLabel(objectName="tenue", alignment=Qt.AlignCenter)
        self.cuerpo.addWidget(self.lbl_hoy)

        app.puente.estado.connect(lambda _: self.refrescar())
        app.puente.stats.connect(lambda _: self._refrescar_vivo())
        app.puente.terminado.connect(self.refrescar)
        QTimer(self, timeout=self.refrescar, interval=3000).start()
        QTimer(self, timeout=self._refrescar_vivo, interval=1000).start()
        self._pintar_contenido()
        self._cargar_opciones()
        self.refrescar()

    # ------------------------------------------------------------------ eleccion
    @property
    def listo(self) -> bool:
        """El destino elegido ya se puede farmear."""
        return self.modo_id in MODOS

    def _girada(self, indice: int):
        self.contenido = CATALOGO[indice]
        listos = [d.id for d in self.contenido.destinos if d.id in MODOS]
        self._elegir_destino((listos or [d.id for d in self.contenido.destinos])[-1], pintar=True)

    def _elegir_destino(self, id_destino: str, pintar: bool = False):
        self.modo_id = id_destino
        cambios = {"ultimo_destino": id_destino}
        if self.listo:
            cambios["ultimo_modo"] = id_destino
        config.guardar(cambios)
        if pintar:
            self._pintar_contenido()
        self._cargar_opciones()
        self.refrescar()
        self.app.refrescar_insignias()

    def _pintar_contenido(self):
        """Nombre, descripcion y pisos del contenido del centro de la rueda."""
        c = self.contenido
        self.lbl_nombre.setText(c.nombre)
        self.lbl_descripcion.setText(c.descripcion)
        while self.fila_destinos.count():
            w = self.fila_destinos.takeAt(0).widget()
            if w:
                self.grupo_destinos.removeButton(w)
                w.setParent(None)
        self.fila_destinos.addStretch()
        if len(c.destinos) > 1:
            for d in c.destinos:
                b = QPushButton(d.nombre, objectName="chip", checkable=True)
                b.setProperty("destino", d.id)
                b.setCursor(Qt.PointingHandCursor)
                if d.id not in MODOS:
                    b.setIcon(iconos.icono("candado", tema.TENUE))
                    b.setToolTip("Próximamente")
                b.setChecked(d.id == self.modo_id)
                self.grupo_destinos.addButton(b)
                self.fila_destinos.addWidget(b)
        self.fila_destinos.addStretch()

    def _cargar_opciones(self):
        guardadas = (config.obtener("opciones_modos") or {}).get(self.modo_id, {})
        victorias = int(guardadas.get("victorias", 0))
        for b in self.grupo_victorias.buttons():
            b.setChecked(b.property("valor") == victorias)
        if not self.grupo_victorias.checkedButton():
            self.grupo_victorias.buttons()[-1].setChecked(True)
        self.chk_pociones.setChecked(bool(guardadas.get("pociones", False)))

    def _empezar_o_detener(self):
        if self.app.puente.corriendo:
            self.app.farmear.detener()
            return
        if not self.listo:
            return
        if not all(p.listo for k, p in self.pasos.items() if k != "ventana"):
            r = QMessageBox.question(self, "Empezar", "Falta algo por preparar (iconos de arriba). ¿Empezar igual?")
            if r != QMessageBox.Yes:
                return
        victorias = self.grupo_victorias.checkedButton().property("valor")
        self.app.farmear.preparar(self.modo_id, {"victorias": victorias, "pociones": self.chk_pociones.isChecked()})
        self.app.farmear.iniciar()
        self.refrescar()

    # ------------------------------------------------------------------ pasos
    def _ayuda_juego(self):
        QMessageBox.information(
            self, "Abrir el juego",
            "Abre 7DS Grand Cross (PC, vertical) y llega a la Tavern.\n\n"
            f"Si no lo detecta, revisa en Ajustes el título de la ventana ('{config.obtener('titulo_ventana')}').")

    def _ajustar(self):
        if not ventana.ajustar_tamano():
            QMessageBox.warning(self, "Ajustar ventana", ventana.ultimo_error)
        self.refrescar()

    def al_mostrar(self):
        self.refrescar()

    def refrescar(self):
        modo = MODOS.get(self.modo_id)
        equipo = getattr(modo, "equipo", None)
        biblioteca = P.cargar()
        tam = ventana.tamano_actual()

        if tam is None:
            self.pasos["juego"].poner("falta", "Cerrado", "No encuentro el juego. Ábrelo y llega a la Tavern.")
            self.pasos["ventana"].poner("nada", "—", "Primero abre el juego.")
        else:
            self.pasos["juego"].poner("ok", "Abierto", "Juego detectado.")
            if not ventana.es_admin():
                self.pasos["ventana"].poner("falta", "Sin permiso", "Reabre Lumen Farm y acepta el aviso de administrador.")
            elif ventana.tamano_correcto(tam):
                self.pasos["ventana"].poner("ok", "Lista", f"Tamaño correcto ({tam[0]}x{tam[1]}).")
            else:
                self.pasos["ventana"].poner("falta", "Ajustar", f"Mide {tam[0]}x{tam[1]}. Clic para ajustarla.")
        if equipo:
            sin = [biblioteca[p].nombre if p in biblioteca else p for p in equipo.personajes_que_faltan()]
            faltan = equipo.faltantes()
            self.pasos["equipo"].poner("falta" if sin else "ok", f"Faltan {len(sin)}" if sin else "Completo",
                                       f"Te falta: {', '.join(sin)}." if sin else "Tienes a todos.")
            self.pasos["cartas"].poner("falta" if faltan else "ok", f"Faltan {len(faltan)}" if faltan else "Listas",
                                       "\n".join(d.descripcion for d in faltan) if faltan else "Todas capturadas.")
        elif self.listo:  # modo que juega con cualquier equipo
            self.pasos["equipo"].poner("ok", "Cualquiera", "Sirve el equipo que tengas puesto en el juego.")
            self.pasos["cartas"].poner("nada", "—", "Este modo no necesita capturas de cartas.")
        else:
            self.pasos["equipo"].poner("nada", "—", "Este modo aún no está listo.")
            self.pasos["cartas"].poner("nada", "—", "Este modo aún no está listo.")
        self._pintar_equipo(equipo, biblioteca)

        t = historial.totales(historial.hoy(historial.leer()))
        self.lbl_hoy.setText(f"Hoy: {t['victorias']} victorias · {formatear_tiempo(t['segundos'])}")
        self._refrescar_version()
        self._refrescar_vivo()

    def _pintar_equipo(self, equipo, biblioteca: dict):
        """Caras del equipo bajo la rueda y una linea de estado."""
        while self.fila_equipo.count():
            w = self.fila_equipo.takeAt(0).widget()
            if w:
                w.setParent(None)
        self.fila_equipo.addStretch()
        if not self.listo:
            self.lbl_estado.setText(f"<span style='color:{tema.TENUE}'>Próximamente</span>")
        elif equipo:
            for pid in equipo.orden:
                pj = biblioteca.get(pid)
                foto = QLabel()
                foto.setFixedSize(40, 40)
                foto.setToolTip(pj.nombre if pj else pid)
                pix = iconos.redondo(pj.ruta_cara(), 40, tema.BORDE) if pj else None
                if pix:
                    foto.setPixmap(pix)
                else:
                    foto.setText((pj.nombre if pj else pid)[:2])
                    foto.setAlignment(Qt.AlignCenter)
                    foto.setObjectName("iniciales")
                self.fila_equipo.addWidget(foto)
            listo = all(p.listo for k, p in self.pasos.items() if k in ("equipo", "cartas"))
            self.lbl_estado.setText(f"<span style='color:{tema.OK}'>Listo</span>" if listo
                                    else f"<span style='color:{tema.AVISO}'>Falta preparar el equipo</span>")
        else:
            self.lbl_estado.setText(f"<span style='color:{tema.OK}'>Listo</span>")
        self.fila_equipo.addStretch()

    def _refrescar_version(self):
        est = self.app.estado_update
        self.lbl_version.setText(f"v{self.app.version_cargada}")
        self.b_actualizar.setText(" Reiniciar" if self.app.reinicio_pendiente else " Actualizar")
        visible = self.app.reinicio_pendiente or bool(est and est.hay_update)
        self.b_actualizar.setVisible(visible)
        self.lbl_version.setVisible(visible)  # la version normal ya sale en la barra de abajo
        if self.app.reinicio_pendiente:
            self.lbl_version.setText(f"v{version_local()} lista · reinicia")
        elif est and est.hay_update:
            self.lbl_version.setText(f"Nueva versión: v{est.version_remota}")
        elif est and est.error:
            self.lbl_version.setText(f"v{self.app.version_cargada}")
            self.lbl_version.setToolTip(est.error)
        self.b_buscar.setEnabled(not self.app.revisando)

    def _refrescar_vivo(self):
        corriendo = self.app.puente.corriendo
        self.b_empezar.setText("  Detener" if corriendo else "  Empezar")
        self.b_empezar.setIcon(iconos.icono("detener" if corriendo else "jugar", tema.SOBRE_ACENTO if not corriendo else tema.TEXTO))
        self.b_empezar.setEnabled(corriendo or self.listo)
        self.b_empezar.setProperty("corriendo", corriendo)
        self.b_empezar.style().unpolish(self.b_empezar)
        self.b_empezar.style().polish(self.b_empezar)
        if corriendo:
            s = self.app.farmear.ultimas_stats
            transcurrido = formatear_tiempo(time.time() - self.app.farmear.inicio) if self.app.farmear.inicio else ""
            estado = "en pausa" if control.en_pausa else control.estado_actual
            self.vivo.setText(f"{estado} · {s.get('victorias', 0)} victorias · {transcurrido}")
        else:
            self.vivo.setText("")

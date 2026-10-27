"""Pagina Inicio: lista guiada 'Antes de empezar', modos en tarjetas y un boton grande para empezar."""

import time

from PyQt5.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from lumen import config, historial, ventana
from lumen import personajes as P
from lumen.actualizador import version_local
from lumen.control import control
from lumen.gui import iconos, tema
from lumen.gui.comun import Pagina, formatear_tiempo
from lumen.modos import MODOS
from lumen.modos.catalogo import CATEGORIAS, por_grupo
from lumen.rutas import IMAGENES

OPCIONES_VICTORIAS = [("1", 1), ("5", 5), ("10", 10), ("25", 25), ("Sin límite", 0)]


class Paso(QFrame):
    """Un punto de la lista 'Antes de empezar': icono, estado y un boton para arreglarlo."""

    def __init__(self, icono: str, titulo: str, accion_texto: str, accion):
        super().__init__(objectName="paso")
        capa = QHBoxLayout(self)
        capa.setContentsMargins(12, 10, 12, 10)
        self.icono_estado = QLabel()
        self.icono_estado.setFixedSize(26, 26)
        capa.addWidget(self.icono_estado)
        textos = QVBoxLayout()
        textos.setSpacing(0)
        cabeza = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(iconos.pixmap(icono, 16, tema.TENUE))
        cabeza.addWidget(ic)
        cabeza.addSpacing(4)
        self.titulo = QLabel(f"<b>{titulo}</b>")
        cabeza.addWidget(self.titulo)
        cabeza.addStretch()
        textos.addLayout(cabeza)
        self.detalle = QLabel(objectName="tenue", wordWrap=True)
        textos.addWidget(self.detalle)
        capa.addLayout(textos, 1)
        self.boton = QPushButton(accion_texto, objectName="chico")
        self.boton.clicked.connect(accion)
        capa.addWidget(self.boton)
        self.listo = False

    def poner(self, listo: bool, detalle: str, mostrar_boton: bool | None = None):
        self.listo = listo
        self.icono_estado.setPixmap(iconos.pixmap("ok" if listo else "falta", 24, tema.OK if listo else tema.AVISO))
        self.detalle.setText(detalle)
        self.boton.setVisible((not listo) if mostrar_boton is None else mostrar_boton)
        self.setProperty("estado", "ok" if listo else "falta")
        self.style().unpolish(self)
        self.style().polish(self)


class TarjetaModo(QFrame):
    """Un modo de farmeo: emblema, nombre del juego, equipo y si lo puedes jugar ya."""

    elegida = pyqtSignal(str)

    def __init__(self, modo):
        super().__init__(objectName="tarjeta_modo")
        self.modo = modo
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(150)
        capa = QHBoxLayout(self)
        capa.setContentsMargins(14, 12, 14, 12)
        emblema = QLabel()
        pix = iconos.redondo(IMAGENES / modo.imagen, 84, tema.ACENTO) if modo.imagen else None
        if pix:
            emblema.setPixmap(pix)
        emblema.setFixedSize(88, 88)
        capa.addWidget(emblema, 0, Qt.AlignTop)
        derecha = QVBoxLayout()
        derecha.setSpacing(3)
        derecha.addWidget(QLabel(modo.titulo_juego or modo.nombre, objectName="titulo_tarjeta"))
        sub = " · ".join(x for x in (modo.subtitulo_juego, modo.duracion) if x)
        derecha.addWidget(QLabel(sub, objectName="tenue"))
        self.fila_equipo = QHBoxLayout()
        self.fila_equipo.setSpacing(6)
        derecha.addLayout(self.fila_equipo)
        self.estado = QLabel()
        derecha.addWidget(self.estado)
        derecha.addStretch()
        capa.addLayout(derecha, 1)

    def refrescar(self, biblioteca: dict, seleccionada: bool):
        self.setProperty("seleccionada", seleccionada)
        self.style().unpolish(self)
        self.style().polish(self)
        while self.fila_equipo.count():
            w = self.fila_equipo.takeAt(0).widget()
            if w:
                w.setParent(None)
        equipo = getattr(self.modo, "equipo", None)
        if not equipo:
            self.estado.setText("")
            return
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
        self.fila_equipo.addStretch()
        sin = [biblioteca[p].nombre if p in biblioteca else p for p in equipo.personajes_que_faltan()]
        faltan = equipo.faltantes()
        if sin:
            self.estado.setText(f"<span style='color:{tema.ERROR}'>Te falta: {', '.join(sin)}</span>")
        elif faltan:
            self.estado.setText(f"<span style='color:{tema.AVISO}'>Faltan {len(faltan)} cartas por capturar</span>")
        else:
            self.estado.setText(f"<span style='color:{tema.OK}'>Listo para farmear</span>")

    def mousePressEvent(self, evento):
        self.elegida.emit(self.modo.id)
        super().mousePressEvent(evento)


class PaginaInicio(Pagina):
    desplazable = True
    titulo = "Inicio"
    subtitulo = "Revisa que todo esté listo, elige qué farmear y pulsa Empezar."

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.modo_id = config.obtener("ultimo_modo") if config.obtener("ultimo_modo") in MODOS else next(iter(MODOS))

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

        # ---- 1. Antes de empezar
        caja = QFrame(objectName="seccion")
        capa = QVBoxLayout(caja)
        cab = QHBoxLayout()
        cab.addWidget(QLabel("<b>Antes de empezar</b>", objectName="titulo_seccion"))
        self.lbl_progreso = QLabel(objectName="tenue")
        cab.addWidget(self.lbl_progreso)
        cab.addStretch()
        capa.addLayout(cab)
        self.barra = QProgressBar(maximum=4, textVisible=False)
        self.barra.setFixedHeight(6)
        capa.addWidget(self.barra)
        rejilla = QGridLayout()
        rejilla.setSpacing(8)
        self.pasos = {
            "juego": Paso("juego", "Juego abierto", "Cómo abrirlo", self._ayuda_juego),
            "ventana": Paso("ventana", "Ventana lista", "Ajustar", self._ajustar),
            "equipo": Paso("equipo", "Personajes del equipo", "Ver equipo", lambda: app.navegar("equipos")),
            "cartas": Paso("cartas", "Cartas capturadas", "Capturar", lambda: app.navegar("personajes")),
        }
        for i, paso in enumerate(self.pasos.values()):
            rejilla.addWidget(paso, i // 2, i % 2)
        capa.addLayout(rejilla)
        self.cuerpo.addWidget(caja)

        # ---- 2. Elige que farmear
        self.cuerpo.addWidget(QLabel("<b>Elige qué farmear</b>", objectName="titulo_seccion"))
        self.rejilla_modos = QGridLayout()
        self.rejilla_modos.setSpacing(10)
        self.tarjetas: dict[str, TarjetaModo] = {}
        for i, modo in enumerate(MODOS.values()):
            t = TarjetaModo(modo)
            t.elegida.connect(self._elegir_modo)
            self.tarjetas[modo.id] = t
            self.rejilla_modos.addWidget(t, i // 2, i % 2)
        self.cuerpo.addLayout(self.rejilla_modos)
        self.cuerpo.addWidget(self._hoja_de_ruta())

        # ---- 3. Cuantas victorias + Empezar
        barra_inicio = QFrame(objectName="seccion")
        fila = QHBoxLayout(barra_inicio)
        fila.setContentsMargins(14, 10, 10, 10)
        trofeo = QLabel()
        trofeo.setPixmap(iconos.pixmap("trofeo", 20, tema.ACENTO))
        fila.addWidget(trofeo)
        fila.addWidget(QLabel("Victorias:"))
        self.grupo_victorias = QButtonGroup(self, exclusive=True)
        for texto, valor in OPCIONES_VICTORIAS:
            b = QPushButton(texto, objectName="chip", checkable=True)
            b.setMinimumWidth(48 if valor else 96)
            b.setProperty("valor", valor)
            self.grupo_victorias.addButton(b)
            fila.addWidget(b)
        fila.addSpacing(14)
        self.chk_pociones = QCheckBox("Usar pociones de stamina")
        self.chk_pociones.setIcon(iconos.icono("pocion", tema.TENUE))
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
        self.lbl_hoy = QLabel(objectName="tenue")
        self.cuerpo.addWidget(self.lbl_hoy)
        self.cuerpo.addStretch()

        app.puente.estado.connect(lambda _: self.refrescar())
        app.puente.stats.connect(lambda _: self._refrescar_vivo())
        app.puente.terminado.connect(self.refrescar)
        QTimer(self, timeout=self.refrescar, interval=3000).start()
        QTimer(self, timeout=self._refrescar_vivo, interval=1000).start()
        self._cargar_opciones()
        self.refrescar()

    # ------------------------------------------------------------------ opciones
    def _cargar_opciones(self):
        guardadas = (config.obtener("opciones_modos") or {}).get(self.modo_id, {})
        victorias = int(guardadas.get("victorias", 0))
        for b in self.grupo_victorias.buttons():
            b.setChecked(b.property("valor") == victorias)
        if not self.grupo_victorias.checkedButton():
            self.grupo_victorias.buttons()[-1].setChecked(True)
        self.chk_pociones.setChecked(bool(guardadas.get("pociones", False)))

    def _hoja_de_ruta(self) -> QFrame:
        """Todo lo que el bot va a farmear (modos/catalogo.py): lo listo en dorado, lo demas en gris."""
        caja = QFrame(objectName="tarjeta_pronto")
        capa = QVBoxLayout(caja)
        capa.setContentsMargins(14, 12, 14, 12)
        capa.setSpacing(6)
        fila = QHBoxLayout()
        candado = QLabel()
        candado.setPixmap(iconos.pixmap("candado", 20, tema.TENUE))
        fila.addWidget(candado)
        fila.addWidget(QLabel("<b>Modos del bot</b> · en dorado los que ya funcionan", objectName="tenue"))
        fila.addStretch()
        capa.addLayout(fila)
        rejilla = QGridLayout()
        rejilla.setHorizontalSpacing(10)
        rejilla.setVerticalSpacing(6)
        n = 0
        for categoria, grupos in por_grupo().items():
            rejilla.addWidget(QLabel(f"<b>{CATEGORIAS[categoria]}</b>"), n, 0, 1, 2)
            n += 1
            for grupo, contenidos in grupos.items():
                if len(grupos) > 1:
                    rejilla.addWidget(QLabel(grupo, objectName="tenue"), n, 0)
                etiquetas = QHBoxLayout()
                etiquetas.setSpacing(6)
                for c in contenidos:
                    listo = c.id in MODOS
                    e = QLabel(c.nombre, objectName="etiqueta_modo")
                    e.setProperty("listo", listo)
                    e.setToolTip("Ya funciona" if listo else "Próximamente")
                    etiquetas.addWidget(e)
                etiquetas.addStretch()
                rejilla.addLayout(etiquetas, n, 1)
                n += 1
        rejilla.setColumnStretch(1, 1)
        capa.addLayout(rejilla)
        return caja

    def _elegir_modo(self, id_modo: str):
        self.modo_id = id_modo
        config.guardar({"ultimo_modo": id_modo})
        self._cargar_opciones()
        self.refrescar()
        self.app.refrescar_insignias()

    def _empezar_o_detener(self):
        if self.app.puente.corriendo:
            self.app.farmear.detener()
            return
        if not all(p.listo for k, p in self.pasos.items() if k != "ventana"):
            r = QMessageBox.question(self, "Empezar", "Hay puntos de 'Antes de empezar' sin resolver. ¿Empezar de todas formas?")
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
            "Abre The Seven Deadly Sins: Grand Cross (cliente de PC) en modo vertical y espera a llegar a la Tavern.\n\n"
            f"Si ya está abierto y no se detecta, revisa en Ajustes que el título de la ventana sea "
            f"'{config.obtener('titulo_ventana')}'.")

    def _ajustar(self):
        if not ventana.ajustar_tamano():
            QMessageBox.warning(self, "Ajustar ventana", ventana.ultimo_error)
        self.refrescar()

    def al_mostrar(self):
        self.refrescar()

    def refrescar(self):
        modo = MODOS[self.modo_id]
        equipo = getattr(modo, "equipo", None)
        biblioteca = P.cargar()
        tam = ventana.tamano_actual()

        self.pasos["juego"].poner(tam is not None, "Detectado." if tam else "No encuentro el juego. Ábrelo y llega a la Tavern.")
        if tam is None:
            self.pasos["ventana"].poner(False, "Primero abre el juego.", mostrar_boton=False)
        elif not ventana.es_admin():
            self.pasos["ventana"].poner(False, "LumenFarm necesita permiso de administrador: reábrelo y acepta el aviso.",
                                        mostrar_boton=False)
        elif ventana.tamano_correcto(tam):
            self.pasos["ventana"].poner(True, f"Tamaño correcto ({tam[0]}x{tam[1]}).")
        else:
            self.pasos["ventana"].poner(False, f"Mide {tam[0]}x{tam[1]}. Se ajusta sola al empezar, o pulsa Ajustar.")
        if equipo:
            sin = [biblioteca[p].nombre if p in biblioteca else p for p in equipo.personajes_que_faltan()]
            self.pasos["equipo"].poner(not sin, "Tienes a los 4." if not sin else f"Te falta: {', '.join(sin)}.")
            faltan = equipo.faltantes()
            self.pasos["cartas"].poner(not faltan, "Todas las cartas necesarias." if not faltan
                                       else f"Faltan {len(faltan)}: " + ", ".join(d.descripcion for d in faltan[:3]) + ("..." if len(faltan) > 3 else ""))
        listos = sum(1 for p in self.pasos.values() if p.listo)
        self.barra.setValue(listos)
        self.lbl_progreso.setText(f"{listos} de 4 listos" + (" · todo listo" if listos == 4 else ""))

        for mid, tarjeta in self.tarjetas.items():
            tarjeta.refrescar(biblioteca, mid == self.modo_id)

        t = historial.totales(historial.hoy(historial.leer()))
        self.lbl_hoy.setText(
            f"Hoy: {t['victorias']} victorias · {t['tasa']:.0f}% de éxito · {t['por_hora']:.1f} victorias/hora · "
            f"{formatear_tiempo(t['segundos'])} farmeando")
        self._refrescar_version()
        self._refrescar_vivo()

    def _refrescar_version(self):
        est = self.app.estado_update
        self.lbl_version.setText(f"v{self.app.version_cargada}")
        self.b_actualizar.setText(" Reiniciar" if self.app.reinicio_pendiente else " Actualizar")
        visible = self.app.reinicio_pendiente or bool(est and est.hay_update)
        self.b_actualizar.setVisible(visible)
        if self.app.reinicio_pendiente:
            self.lbl_version.setText(f"v{version_local()} instalada · reinicia para usarla")
        elif est and est.hay_update:
            self.lbl_version.setText(f"Actualización obligatoria: v{est.version_remota}")
        elif est and est.error:
            self.lbl_version.setText(f"v{self.app.version_cargada} · {est.error}")
        elif est:
            self.lbl_version.setText(f"v{self.app.version_cargada} · al día")
        self.b_buscar.setEnabled(not self.app.revisando)

    def _refrescar_vivo(self):
        corriendo = self.app.puente.corriendo
        self.b_empezar.setText("  Detener" if corriendo else "  Empezar")
        self.b_empezar.setIcon(iconos.icono("detener" if corriendo else "jugar", tema.SOBRE_ACENTO if not corriendo else tema.TEXTO))
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

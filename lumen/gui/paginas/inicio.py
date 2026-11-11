"""Preparacion de sesiones: requisitos, materiales, equipo y condicion de parada."""

import time

from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtWidgets import (
    QButtonGroup,
    QBoxLayout,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
)

from lumen import config, metas, ventana
from lumen import personajes as P
from lumen.actualizador import version_local
from lumen.control import control
from lumen.gui import iconos, tema
from lumen.gui.comun import Pagina, formatear_tiempo
from lumen.gui.metas import EditorMeta, FilaMateriales

from lumen.modos import MODOS
from lumen.modos.catalogo import CATALOGO, contenido_de, foto_de

TAM_CARA = 48  # caras del equipo mas rapido: cuadro con la cara del artwork (elegido 2026-10-29)
OPCIONES_VICTORIAS = [("1", 1), ("3", 3), ("5", 5), ("10", 10), ("25", 25), ("∞", 0)]


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
    titulo = "Preparar sesión"
    subtitulo = "Revisa el contenido, tu equipo y cuándo quieres que termine el farmeo."

    def __init__(self, app):
        super().__init__()
        self.app = app
        guardado = config.obtener("ultimo_destino") or config.obtener("ultimo_modo")
        self.contenido = contenido_de(guardado) or CATALOGO[0]
        self.modo_id = (
            guardado if contenido_de(guardado) else self.contenido.destinos[-1].id
        )

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

        volver = QPushButton("← Volver a contenidos", objectName="enlace")
        volver.clicked.connect(lambda: app.navegar("contenidos"))
        self.acciones.addWidget(volver)
        cuerpo = QHBoxLayout()
        self.columnas_preparacion = cuerpo
        cuerpo.setSpacing(20)
        izquierda = QVBoxLayout()
        izquierda.setSpacing(16)
        derecha = QVBoxLayout()
        derecha.setSpacing(16)
        resumen = QFrame(objectName="seccion")
        rc = QVBoxLayout(resumen)
        rc.setContentsMargins(22, 22, 22, 22)
        cab = QHBoxLayout()
        self.portada = QLabel(alignment=Qt.AlignCenter)
        self.portada.setFixedSize(114, 114)
        cab.addWidget(self.portada)
        textos = QVBoxLayout()
        textos.addWidget(QLabel("CONTENIDO SELECCIONADO", objectName="eyebrow"))
        self.lbl_nombre = QLabel(objectName="titulo_hero", wordWrap=True)
        self.lbl_descripcion = QLabel(objectName="tenue", wordWrap=True)
        textos.addWidget(self.lbl_nombre)
        textos.addWidget(self.lbl_descripcion)
        cab.addLayout(textos, 1)
        rc.addLayout(cab)
        rc.addWidget(
            QLabel("Elige el piso o la dificultad", objectName="titulo_seccion")
        )
        self.fila_destinos = QHBoxLayout()
        self.fila_destinos.setSpacing(8)
        self.grupo_destinos = QButtonGroup(self, exclusive=True)
        self.grupo_destinos.buttonClicked.connect(
            lambda b: self._elegir_destino(b.property("destino"))
        )
        rc.addLayout(self.fila_destinos)
        izquierda.addWidget(resumen)
        caja_materiales = QFrame(objectName="seccion")
        cm = QVBoxLayout(caja_materiales)
        cm.setContentsMargins(22, 18, 22, 18)
        cm.addWidget(QLabel("Materiales y objetivos", objectName="titulo_seccion"))
        cm.addWidget(
            QLabel(
                "Toca un material para indicar cuánto tienes y cuánto quieres conseguir.",
                objectName="tenue",
                wordWrap=True,
            )
        )
        self.fila_metas = FilaMateriales(46, "premio", centrar=False)
        self.fila_metas.tocado.connect(self._tocar_material)
        cm.addWidget(self.fila_metas)
        self.editor = EditorMeta()
        self.editor.cambiado.connect(self._metas_cambiadas)
        self.editor.cerrado.connect(self._editor_cerrado)
        self.editor.ir.connect(self._ir_a_meta)
        cm.addWidget(self.editor)
        izquierda.addWidget(caja_materiales)
        self.caja_equipo = QFrame(objectName="seccion")
        ce = QVBoxLayout(self.caja_equipo)
        ce.setContentsMargins(22, 18, 22, 18)
        ce.addWidget(QLabel("Equipo recomendado", objectName="titulo_seccion"))
        self.fila_equipo = QHBoxLayout()
        ce.addLayout(self.fila_equipo)
        self.lbl_estado = QLabel(objectName="tenue", wordWrap=True)
        ce.addWidget(self.lbl_estado)
        izquierda.addWidget(self.caja_equipo)
        izquierda.addStretch()
        checklist = QFrame(objectName="seccion")
        cl = QVBoxLayout(checklist)
        cl.setContentsMargins(18, 18, 18, 18)
        cl.addWidget(QLabel("Antes de empezar", objectName="titulo_seccion"))
        self.pasos = {
            "juego": Paso("juego", "Juego", self._ayuda_juego),
            "ventana": Paso("ventana", "Ventana", self._ajustar),
            "equipo": Paso("equipo", "Equipo", lambda: app.farmear.ver_equipos()),
            "cartas": Paso("cartas", "Cartas", lambda: app.navegar("personajes")),
        }
        for paso in self.pasos.values():
            paso.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            paso.setMinimumHeight(54)
            cl.addWidget(paso)
        derecha.addWidget(checklist)
        opciones = QFrame(objectName="seccion")
        op = QVBoxLayout(opciones)
        op.setContentsMargins(18, 18, 18, 18)
        op.addWidget(QLabel("Cuándo terminar", objectName="titulo_seccion"))
        op.addWidget(QLabel("Victorias o vueltas completas", objectName="tenue"))
        botones = QGridLayout()
        self.grupo_victorias = QButtonGroup(self, exclusive=True)
        for i, (texto, valor) in enumerate(OPCIONES_VICTORIAS):
            boton = QPushButton(texto, objectName="chip", checkable=True)
            boton.setProperty("valor", valor)
            boton.setToolTip("Sin límite" if not valor else f"Parar tras {valor}")
            self.grupo_victorias.addButton(boton)
            botones.addWidget(boton, i // 3, i % 3)
        self.b_meta = QPushButton(
            "Hasta completar mis objetivos", objectName="chip", checkable=True
        )
        self.b_meta.setProperty("valor", "meta")
        self.grupo_victorias.addButton(self.b_meta)
        botones.addWidget(self.b_meta, 2, 0, 1, 3)
        op.addLayout(botones)
        self.chk_pociones = QCheckBox("Permitir pociones de stamina")
        op.addWidget(self.chk_pociones)
        self.vivo = QLabel(objectName="tenue", wordWrap=True)
        op.addWidget(self.vivo)
        self.b_empezar = QPushButton("Iniciar sesión", objectName="empezar")
        self.b_empezar.setMinimumHeight(48)
        self.b_empezar.clicked.connect(self._empezar_o_detener)
        op.addWidget(self.b_empezar)
        self.mensaje_preparacion = QLabel(objectName="tenue", wordWrap=True)
        op.addWidget(self.mensaje_preparacion)
        derecha.addWidget(opciones)
        derecha.addStretch()
        cuerpo.addLayout(izquierda, 7)
        cuerpo.addLayout(derecha, 3)
        self.cuerpo.addLayout(cuerpo)
        self.lista = [c for c in CATALOGO if c.grupo == self.contenido.grupo]
        self._firma_metas = (
            None  # para repintar la fila "Metas" solo si cambia el avance de las metas
        )

        app.puente.estado.connect(lambda _: self.refrescar())
        app.puente.stats.connect(lambda _: self._refrescar_vivo())
        app.puente.terminado.connect(self.refrescar)
        QTimer(self, timeout=self.refrescar, interval=3000).start()
        QTimer(self, timeout=self._refrescar_vivo, interval=1000).start()
        self._pintar_contenido()
        self._pintar_premios()
        self._cargar_opciones()
        self.refrescar()

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        if hasattr(self, "columnas_preparacion"):
            vertical = self.width() < 1100
            self.columnas_preparacion.setDirection(
                QBoxLayout.TopToBottom if vertical else QBoxLayout.LeftToRight
            )
            self.columnas_preparacion.setStretch(0, 0 if vertical else 7)
            self.columnas_preparacion.setStretch(1, 0 if vertical else 3)

    # ------------------------------------------------------------------ eleccion
    @property
    def listo(self) -> bool:
        """El destino elegido ya se puede farmear."""
        return self.modo_id in MODOS

    def _elegir_destino(self, id_destino: str, pintar: bool = False):
        self.modo_id = id_destino
        cambios = {"ultimo_destino": id_destino}
        if self.listo:
            cambios["ultimo_modo"] = id_destino
        config.guardar(cambios)
        self._pintar_contenido()
        self._pintar_premios()
        self._cargar_opciones()
        self.refrescar()
        self.app.refrescar_insignias()

    def _pintar_premios(self):
        """La fila "Metas" del destino elegido, con el avance de cada meta."""
        todas = metas.cargar()
        self._firma_metas = tuple((m.objeto, m.actual, m.quiero) for m in todas)
        self.fila_metas.pintar(self.modo_id, todas, abierto=self.editor.objeto)
        if self.editor.objeto and self.editor.objeto not in self.fila_metas.objetos:
            self.editor.objeto = (
                None  # otro destino: la franja era de un material que aqui no sale
            )
            self.editor.hide()
            self.caja_equipo.show()
        self._pintar_chip_meta(todas)

    def _pintar_chip_meta(self, todas: list):
        """El chip "Meta" solo vale si este destino ayuda a alguna meta sin completar."""
        utiles = metas.del_destino(self.modo_id, todas) if self.listo else []
        self.b_meta.setEnabled(bool(utiles))
        self.b_meta.setToolTip(
            "Parar al completar: "
            + ", ".join(f"{m.nombre} ({m.actual}/{m.quiero})" for m in utiles)
            if utiles
            else "Ninguna meta tuya sale aquí. Toca un material de «Metas» para crear una."
        )
        if not utiles and self.b_meta.isChecked():
            self._marcar_sin_limite()

    def _marcar_sin_limite(self):
        next(
            b for b in self.grupo_victorias.buttons() if b.property("valor") == 0
        ).setChecked(True)

    def refrescar_metas(self):
        self._pintar_premios()

    # ------------------------------------------------------------------ metas
    def _tocar_material(self, objeto: str):
        if self.editor.objeto == objeto:  # tocar el mismo otra vez cierra la franja
            self.editor.cerrar()
            return
        self.abrir_meta(objeto)

    def abrir_meta(self, objeto: str, id_destino: str | None = None):
        """Abre la franja de la meta de un material (desde Farmear, en el destino que se esta farmeando)."""
        if id_destino and id_destino != self.modo_id:
            self.ir_a_destino(id_destino)
        self.app.navegar("preparar")
        self.caja_equipo.hide()
        self.editor.abrir(objeto)
        self._pintar_premios()

    def _editor_cerrado(self):
        self.caja_equipo.show()
        self._pintar_premios()

    def _metas_cambiadas(self):
        self._pintar_premios()
        self.app.farmear.repintar_metas()

    def _ir_a_meta(self, id_destino: str):
        """'Ir a farmearla': gira la rueda al sitio donde mas sale y deja puesto el chip Meta."""
        self.editor.cerrar()
        self.ir_a_destino(id_destino)
        if self.b_meta.isEnabled():
            self.b_meta.setChecked(True)

    def ir_a_destino(self, id_destino: str):
        c = contenido_de(id_destino)
        if c is None:
            return
        self.contenido = c
        self.lista = [c]
        self._elegir_destino(id_destino, pintar=True)

    def _pintar_contenido(self):
        """Nombre, descripcion y pisos del contenido del centro de la rueda."""
        c = self.contenido
        self.lbl_nombre.setText(c.nombre)
        self.lbl_descripcion.setText(c.descripcion)
        pix = iconos.redondo(foto_de(self.modo_id) or c.foto, 108, tema.BORDE)
        if pix is not None:
            self.portada.setPixmap(pix)
        else:
            self.portada.clear()
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
        # Sin nada elegido, los Floor 1-3 hacen una vuelta entera (los 3 pisos); lo demas, sin limite.
        victorias = int(
            guardadas.get("victorias", 3 if self.modo_id.endswith("_pisos1a3") else 0)
        )
        for b in self.grupo_victorias.buttons():
            b.setChecked(b.property("valor") == victorias)
        if not self.grupo_victorias.checkedButton():
            self._marcar_sin_limite()
        self.chk_pociones.setChecked(bool(guardadas.get("pociones", False)))
        modo = MODOS.get(self.modo_id)  # Indura, p. ej., no usa pociones
        self.chk_pociones.setVisible(
            modo is None or any(op.clave == "pociones" for op in modo.opciones)
        )

    def _empezar_o_detener(self):
        if self.app.puente.corriendo:
            self.app.farmear.detener()
            return
        if not self.listo:
            return
        if not all(p.listo for k, p in self.pasos.items() if k != "ventana"):
            r = QMessageBox.question(
                self,
                "Empezar",
                "Falta algo por preparar (iconos de arriba). ¿Empezar igual?",
            )
            if r != QMessageBox.Yes:
                return
        victorias = self.grupo_victorias.checkedButton().property("valor")
        meta = (
            victorias == "meta"
        )  # sin limite de victorias: para al completar las metas
        self.app.farmear.preparar(
            self.modo_id,
            {
                "victorias": 0 if meta else victorias,
                "pociones": self.chk_pociones.isChecked(),
            },
        )
        self.app.farmear.iniciar(meta=meta)
        self.refrescar()

    # ------------------------------------------------------------------ pasos
    def _ayuda_juego(self):
        QMessageBox.information(
            self,
            "Abrir el juego",
            "Abre 7DS Grand Cross (PC, vertical) y llega a la Tavern.\n\n"
            f"Si no lo detecta, revisa en Ajustes el título de la ventana ('{config.obtener('titulo_ventana')}').",
        )

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
            self.pasos["juego"].poner(
                "falta", "Cerrado", "No encuentro el juego. Ábrelo y llega a la Tavern."
            )
            self.pasos["ventana"].poner("nada", "—", "Primero abre el juego.")
        else:
            self.pasos["juego"].poner("ok", "Abierto", "Juego detectado.")
            if not ventana.es_admin():
                self.pasos["ventana"].poner(
                    "falta",
                    "Sin permiso",
                    "Reabre Lumen Farm y acepta el aviso de administrador.",
                )
            elif ventana.tamano_correcto(tam):
                self.pasos["ventana"].poner(
                    "ok", "Lista", f"Tamaño correcto ({tam[0]}x{tam[1]})."
                )
            else:
                self.pasos["ventana"].poner(
                    "falta", "Ajustar", f"Mide {tam[0]}x{tam[1]}. Clic para ajustarla."
                )
        if equipo:
            sin = [
                biblioteca[p].nombre if p in biblioteca else p
                for p in equipo.personajes_que_faltan()
            ]
            faltan = equipo.faltantes()
            self.pasos["equipo"].poner(
                "falta" if sin else "ok",
                f"Faltan {len(sin)}" if sin else "Completo",
                f"Te falta: {', '.join(sin)}." if sin else "Tienes a todos.",
            )
            self.pasos["cartas"].poner(
                "falta" if faltan else "ok",
                f"Faltan {len(faltan)}" if faltan else "Listas",
                "\n".join(d.descripcion for d in faltan)
                if faltan
                else "Todas capturadas.",
            )
        elif self.listo:  # modo que juega con cualquier equipo
            self.pasos["equipo"].poner(
                "ok", "Cualquiera", "Sirve el equipo que tengas puesto en el juego."
            )
            self.pasos["cartas"].poner(
                "nada", "—", "Este modo no necesita capturas de cartas."
            )
        else:
            self.pasos["equipo"].poner("nada", "—", "Este modo aún no está listo.")
            self.pasos["cartas"].poner("nada", "—", "Este modo aún no está listo.")
        self._pintar_equipo(equipo, biblioteca)

        if (
            tuple((m.objeto, m.actual, m.quiero) for m in metas.cargar())
            != self._firma_metas
        ):
            self._pintar_premios()  # avanzo una meta (el botin de la ultima victoria)
        self._refrescar_version()
        self._refrescar_vivo()

    def _pintar_equipo(self, equipo, biblioteca: dict):
        """Bajo la rueda: el equipo mas rapido medido para este destino y si esta todo listo."""
        from lumen.gui.paginas.equipos import mas_rapido, texto_minutos
        from lumen.gui.paginas.personajes import _en_gris

        while self.fila_equipo.count():
            w = self.fila_equipo.takeAt(0).widget()
            if w:
                w.setParent(None)
        self.fila_equipo.addStretch()
        self.lbl_estado.show()
        if not self.listo:
            self.lbl_estado.setText(
                f"<span style='color:{tema.TENUE}'>Próximamente</span>"
            )
            self.fila_equipo.addStretch()
            return
        rapido = mas_rapido(self.modo_id)
        if rapido:
            self.fila_equipo.addWidget(
                self._tarjeta_rapido(rapido, biblioteca, _en_gris, texto_minutos)
            )
            self.lbl_estado.hide()  # la tarjeta ya dice si tienes el equipo (y el icono Equipo de arriba)
        else:
            self.fila_equipo.addWidget(
                QLabel(
                    "⚡ Equipo más rápido: aún sin medir"
                    + (" · sirve cualquiera" if not equipo else ""),
                    objectName="tenue",
                )
            )
        self.fila_equipo.addStretch()
        listo = all(p.listo for k, p in self.pasos.items() if k in ("equipo", "cartas"))
        self.lbl_estado.setText(
            f"<span style='color:{tema.OK}'>Listo</span>"
            if listo
            else f"<span style='color:{tema.AVISO}'>Falta preparar el equipo</span>"
        )

    def _tarjeta_rapido(
        self, rapido: dict, biblioteca: dict, en_gris, texto_minutos
    ) -> QFrame:
        """Rayo, nombre y tiempo, y las 4 caras (en gris las que no tienes). Clic = ver los equipos."""
        datos = rapido["datos"]
        tarjeta = QFrame(objectName="seccion")
        tarjeta.setCursor(Qt.PointingHandCursor)
        tarjeta.mousePressEvent = lambda _e: self.app.farmear.ver_equipos()
        tarjeta.setToolTip(
            "El equipo que menos tarda en ganar de los medidos. Clic para ver todos."
        )
        exterior = QVBoxLayout(tarjeta)
        fila = QHBoxLayout()
        exterior.addLayout(fila)
        fila.setContentsMargins(12, 6, 12, 6)
        fila.setSpacing(8)
        rayo = QLabel()
        rayo.setPixmap(iconos.pixmap("rayo", 22, tema.ACENTO))
        fila.addWidget(rayo)
        textos = QVBoxLayout()
        textos.setSpacing(0)
        titulo = QLabel(f"Más rápido · <b>{datos.get('nombre', '')}</b>")
        titulo.setWordWrap(True)
        textos.addWidget(titulo)
        fuente = "medido en pruebas"
        if rapido["fuente"] == "tuyo":
            peleas = rapido.get("peleas", 0)
            fuente = f"medido por ti en {peleas} peleas" + (
                " (aún pocas)" if peleas < 5 else ""
            )
        textos.addWidget(
            QLabel(f"{texto_minutos(rapido['minutos'])} · {fuente}", objectName="tenue")
        )
        fila.addLayout(textos)
        fila = QHBoxLayout()
        exterior.addLayout(fila)
        faltan = 0
        for pid in datos.get("personajes") or []:
            pj = biblioteca.get(pid)
            tengo = bool(pj and pj.tengo)
            faltan += not tengo
            foto = QLabel()
            foto.setFixedSize(TAM_CARA, TAM_CARA)
            foto.setToolTip(
                (pj.nombre if pj else pid) + ("" if tengo else " (no lo tienes)")
            )
            pix = None
            if pj:
                ruta, rostro = pj.rostro()
                pix = iconos.cuadrado(
                    ruta, TAM_CARA, tema.ACENTO if tengo else tema.BORDE, rostro=rostro
                )
            if pix:
                foto.setPixmap(pix if tengo else en_gris(pix))
            else:
                foto.setText((pj.nombre if pj else pid)[:2])
                foto.setAlignment(Qt.AlignCenter)
                foto.setObjectName("iniciales")
            fila.addWidget(foto)
        if not datos.get(
            "personajes"
        ):  # equipo por su nombre del juego (Fuerte Solgres): sin caras
            return tarjeta
        estado = QLabel("Lo tienes" if not faltan else f"Te faltan {faltan}")
        estado.setStyleSheet(
            f"color: {tema.OK if not faltan else tema.AVISO}; font-weight: 700;"
        )
        fila.addSpacing(4)
        fila.addWidget(estado)
        return tarjeta

    def _refrescar_version(self):
        est = self.app.estado_update
        self.lbl_version.setText(f"v{self.app.version_cargada}")
        self.b_actualizar.setText(
            " Reiniciar" if self.app.reinicio_pendiente else " Actualizar"
        )
        visible = self.app.reinicio_pendiente or bool(est and est.hay_update)
        self.b_actualizar.setVisible(visible)
        self.lbl_version.setVisible(
            visible
        )  # la version normal ya sale en la barra de abajo
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
        self.b_empezar.setText("Detener sesión" if corriendo else "Iniciar sesión")
        self.b_empezar.setIcon(
            iconos.icono(
                "detener" if corriendo else "jugar",
                tema.SOBRE_ACENTO if not corriendo else tema.TEXTO,
            )
        )
        self.b_empezar.setEnabled(
            corriendo or (self.listo and self.pasos["juego"].listo)
        )
        self.mensaje_preparacion.setText(
            "La sesión continúa en Sesión en directo."
            if corriendo
            else "Este contenido todavía no está disponible."
            if not self.listo
            else "Abre el juego para poder iniciar."
            if not self.pasos["juego"].listo
            else "Revisa los requisitos de arriba antes de empezar."
        )
        self.b_empezar.setProperty("corriendo", corriendo)
        self.b_empezar.style().unpolish(self.b_empezar)
        self.b_empezar.style().polish(self.b_empezar)
        if corriendo:
            s = self.app.farmear.ultimas_stats
            transcurrido = (
                formatear_tiempo(time.time() - self.app.farmear.inicio)
                if self.app.farmear.inicio
                else ""
            )
            estado = "en pausa" if control.en_pausa else control.estado_actual
            self.vivo.setText(
                f"{estado} · {s.get('victorias', 0)} victorias · {transcurrido}"
            )
        else:
            self.vivo.setText("")

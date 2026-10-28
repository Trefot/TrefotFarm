"""Ventana principal: menu lateral con paginas, barra de estado y actualizaciones obligatorias."""

import sys
import threading

from PyQt5.QtCore import QObject, QProcess, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import lumen
from lumen import accesos, actualizador, config, ventana
from lumen.control import control
from lumen.gui import iconos, tema
from lumen.gui.arranque import EMBLEMA
from lumen.gui.paginas.actualizaciones import PantallaBloqueo
from lumen.gui.paginas.ajustes import PaginaAjustes
from lumen.gui.paginas.ayuda import PaginaAyuda
from lumen.gui.paginas.capturas import PaginaCapturas
from lumen.gui.paginas.editor_personajes import PaginaEditorPersonajes
from lumen.gui.paginas.farmear import PaginaFarmear
from lumen.gui.paginas.heroes_capturados import PaginaHeroesCapturados
from lumen.gui.paginas.equipos import PaginaEquipos
from lumen.gui.paginas.inicio import PaginaInicio
from lumen.gui.paginas.personajes import PaginaPersonajes
from lumen.gui.paginas.recompensas import PaginaRecompensas
from lumen.gui.puente import Puente
from lumen.modos import MODOS
from lumen.rutas import RAIZ

MINUTOS_ENTRE_REVISIONES = 30

MENU = [
    ("inicio", "Inicio"),
    ("farmear", "Farmear"),
    ("personajes", "Personajes"),
    ("ayuda", "Ayuda"),
    ("ajustes", "Ajustes"),
    # Solo con el modo administrador (Ajustes): herramientas para mantener la base del bot.
    ("equipos", "Equipos"),
    ("recompensas", "Botín"),
    ("capturas", "Capturas"),
    ("editor", "Editor"),
    ("capturados", "Héroes"),
]
SOLO_ADMIN = {"capturas", "editor", "capturados", "equipos", "recompensas"}  # lo demas esta en Farmear


class _Senales(QObject):
    revision = pyqtSignal(object)  # actualizador.Estado
    progreso = pyqtSignal(str)
    fin_update = pyqtSignal(bool, str)


class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.version_cargada = lumen.__version__  # la que esta corriendo (la del disco puede ser mas nueva)
        self.setWindowTitle(f"LumenFarm v{self.version_cargada}")
        self.resize(1320, 800)
        self.setMinimumSize(1100, 680)
        self.puente = Puente()
        self.senales = _Senales()
        self.estado_update: actualizador.Estado | None = None
        self.update_bloqueante = False
        self.actualizando = False
        self.revisando = False

        central = QWidget()
        raiz = QVBoxLayout(central)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        fila = QHBoxLayout()
        fila.setSpacing(0)

        # ---- menu lateral
        lateral = QFrame(objectName="lateral")
        lateral.setFixedWidth(96)
        capa_lat = QVBoxLayout(lateral)
        capa_lat.setContentsMargins(8, 14, 8, 12)
        capa_lat.setSpacing(4)
        emblema = QLabel(alignment=Qt.AlignCenter)
        emblema.setPixmap(QPixmap(str(EMBLEMA)).scaled(58, 58, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        emblema.setToolTip(f"Lumen Farm v{self.version_cargada}")
        capa_lat.addWidget(emblema)
        capa_lat.addWidget(QLabel("LUMEN", objectName="marca", alignment=Qt.AlignCenter))
        if tema.SKIN.saludo:
            adorno = QLabel(alignment=Qt.AlignCenter)
            adorno.setPixmap(iconos.pixmap(tema.SKIN.icono, 22, tema.ACENTO))
            adorno.setToolTip(tema.SKIN.saludo)
            capa_lat.addWidget(adorno)
        capa_lat.addSpacing(6)
        capa_lat.addWidget(QFrame(objectName="separador_oro"))
        capa_lat.addSpacing(6)
        self.grupo = QButtonGroup(self, exclusive=True)
        self.botones: dict[str, QToolButton] = {}
        self.insignias: dict[str, QLabel] = {}
        for clave, texto in MENU:
            b = QToolButton(objectName="menu", checkable=True, text=texto)
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setIcon(iconos.icono("mdi6.database-edit" if clave == "editor" else clave, tema.TENUE, tema.ACENTO))
            b.setIconSize(QSize(24, 24))
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _, c=clave: self.navegar(c))
            self.grupo.addButton(b)
            self.botones[clave] = b
            insignia = QLabel(b, objectName="insignia")  # punto rojo en la esquina del boton
            insignia.move(52, 2)
            insignia.hide()
            self.insignias[clave] = insignia
            capa_lat.addWidget(b)
        capa_lat.addStretch()
        fila.addWidget(lateral)

        # ---- paginas
        self.pila = QStackedWidget()
        self.farmear = PaginaFarmear(self)
        self.paginas = {
            "inicio": PaginaInicio(self),
            "farmear": self.farmear,
            "capturas": PaginaCapturas(self),
            "personajes": PaginaPersonajes(self),
            "editor": PaginaEditorPersonajes(self),
            "capturados": PaginaHeroesCapturados(self),
            "equipos": PaginaEquipos(self),
            "recompensas": PaginaRecompensas(self),
            "ayuda": PaginaAyuda(self),
            "ajustes": PaginaAjustes(self),
        }
        for pagina in self.paginas.values():
            self.pila.addWidget(pagina)
        self.bloqueo = PantallaBloqueo(self)
        self.pila.addWidget(self.bloqueo)
        fila.addWidget(self.pila, 1)
        raiz.addLayout(fila, 1)

        # ---- barra inferior
        barra = QFrame(objectName="barra")
        capa_barra = QHBoxLayout(barra)
        capa_barra.setContentsMargins(14, 4, 14, 4)
        self.barra_juego = QLabel()
        self.barra_bot = QLabel()
        self.barra_update = QLabel()
        capa_barra.addWidget(self.barra_juego)
        capa_barra.addWidget(QLabel("·"))
        capa_barra.addWidget(self.barra_bot)
        capa_barra.addStretch()
        capa_barra.addWidget(self.barra_update)
        raiz.addWidget(barra)
        self.setCentralWidget(central)

        # ---- senales
        self.senales.revision.connect(self._resultado_revision)
        self.senales.progreso.connect(self.bloqueo.mensaje)
        self.senales.fin_update.connect(self._fin_update)
        self.puente.terminado.connect(self._bot_terminado)
        self.puente.estado.connect(lambda _: self._barra())

        QTimer(self, timeout=self._barra, interval=2000).start()
        QTimer(self, timeout=self.buscar_updates, interval=MINUTOS_ENTRE_REVISIONES * 60 * 1000).start()
        self.puente.escuchar_teclas()
        self.puente.escucha.aplicar_ajustes()
        self.navegar("inicio")
        self.refrescar_insignias()
        self.aplicar_modo_admin()
        self._barra()
        self.farmear.escribir("LumenFarm listo.", "ok")
        QTimer.singleShot(300, self.buscar_updates)
        accesos.migrar_viejos()
        if not config.obtener("asistente_visto"):
            QTimer.singleShot(700, self.abrir_asistente)
        elif not config.obtener("acceso_ofrecido"):
            QTimer.singleShot(900, self.ofrecer_acceso)

    # ---------------------------------------------------------------- navegacion
    def navegar(self, clave: str):
        if self.update_bloqueante:
            self.mostrar_bloqueo()
            return
        pagina = self.paginas[clave]
        self.botones[clave].setChecked(True)
        self.pila.setCurrentWidget(pagina)
        pagina.al_mostrar()

    def refrescar_insignias(self):
        faltan = 0
        modo = MODOS.get(config.obtener("ultimo_modo")) or next(iter(MODOS.values()))
        if getattr(modo, "equipo", None) is not None:
            faltan = len(modo.equipo.faltantes())
        self._insignia("capturas", str(faltan) if faltan else "")
        self._insignia("inicio", "1" if self.estado_update and self.estado_update.hay_update else "")

    def _insignia(self, clave: str, texto: str):
        self.insignias[clave].setText(texto)
        self.insignias[clave].setVisible(bool(texto) and (clave not in SOLO_ADMIN or bool(config.obtener("modo_admin"))))

    def aplicar_modo_admin(self):
        """Muestra u oculta las herramientas de administrador del menu."""
        admin = bool(config.obtener("modo_admin"))
        for clave in SOLO_ADMIN:
            self.botones[clave].setVisible(admin)
            self.insignias[clave].setVisible(admin and bool(self.insignias[clave].text()))
        if not admin and self.pila.currentWidget() in (self.paginas[c] for c in SOLO_ADMIN):
            self.navegar("inicio")

    def ajustes_guardados(self):
        self.aplicar_modo_admin()
        self.farmear.actualizar_ayuda_teclas()
        self.puente.escucha.aplicar_ajustes()
        self._barra()

    def _barra(self):
        tam = ventana.tamano_actual()
        if tam is None:
            self.barra_juego.setText(f"<span style='color:{tema.ERROR}'>●</span> Juego cerrado")
        else:
            ok = ventana.tamano_correcto(tam)
            color = tema.OK if ok else tema.AVISO
            self.barra_juego.setText(f"<span style='color:{color}'>●</span> Juego {tam[0]}x{tam[1]}")
        if self.puente.corriendo:
            estado = "en pausa" if control.en_pausa else control.estado_actual
            self.barra_bot.setText(f"<span style='color:{tema.OK}'>●</span> Bot: {estado}")
        else:
            self.barra_bot.setText("Bot detenido")
        est = self.estado_update
        version = self.version_cargada
        if self.reinicio_pendiente:
            self.barra_update.setText(
                f"<span style='color:{tema.AVISO}'>v{actualizador.version_local()} instalada · reinicia para usarla</span>")
        elif est and est.hay_update:
            self.barra_update.setText(f"<span style='color:{tema.AVISO}'>Actualizacion obligatoria v{est.version_remota}</span>")
        elif est and est.error:
            self.barra_update.setText(f"v{version} · {est.error}")
        else:
            self.barra_update.setText(f"v{version} · al día" if est else f"v{version}")

    # ------------------------------------------------------------ actualizaciones
    @property
    def reinicio_pendiente(self) -> bool:
        """Los archivos del disco son de una version distinta a la que esta corriendo."""
        try:
            return actualizador.version_local() != self.version_cargada
        except OSError:
            return False

    def accion_actualizar(self):
        """Boton Actualizar de Inicio: reinicia si la version nueva ya esta en disco; si no, actualiza."""
        if self.reinicio_pendiente:
            if self.puente.corriendo:
                QMessageBox.information(self, "Reiniciar", "Deten el bot antes de reiniciar.")
                return
            self._reiniciar()
        else:
            self.mostrar_bloqueo()

    def buscar_updates(self, manual: bool = False):
        if self.revisando or self.actualizando:
            return
        self.revisando = True
        if manual:
            self.paginas["inicio"].refrescar()

        def revisar():
            try:
                estado = actualizador.revisar()
            except Exception as e:  # nunca romper la interfaz por esto
                estado = actualizador.Estado(version_local=actualizador.version_local(), error=str(e))
            self.senales.revision.emit(estado)

        threading.Thread(target=revisar, daemon=True).start()

    def _resultado_revision(self, estado):
        self.revisando = False
        self.estado_update = estado
        self.refrescar_insignias()
        self._barra()
        self.paginas["inicio"].refrescar()
        if estado.hay_update and not self.update_bloqueante:
            self.update_bloqueante = True
            if self.puente.corriendo:
                control.parar_en_zona_segura = True
                self.farmear.escribir(
                    f"Hay una actualizacion obligatoria (v{estado.version_remota}). "
                    "Termino la pelea actual y me detengo.", "aviso")
            self.mostrar_bloqueo()

    def mostrar_bloqueo(self):
        if not (self.estado_update and self.estado_update.hay_update):
            return
        self.update_bloqueante = True
        for b in self.botones.values():
            b.setEnabled(False)
        self.bloqueo.refrescar()
        self.pila.setCurrentWidget(self.bloqueo)

    def _bot_terminado(self):
        self._barra()
        if self.update_bloqueante:
            self.bloqueo.refrescar()

    def aplicar_update(self):
        if self.puente.corriendo or self.actualizando:
            return
        self.actualizando = True
        self.bloqueo.boton.setEnabled(False)

        def correr():
            try:
                resumen = actualizador.actualizar(self.senales.progreso.emit)
                self.senales.fin_update.emit(True, resumen)
            except Exception as e:
                self.senales.fin_update.emit(False, str(e))

        threading.Thread(target=correr, daemon=True).start()

    def _fin_update(self, ok: bool, texto: str):
        self.actualizando = False
        if not ok:
            self.bloqueo.mensaje(f"No se pudo actualizar: {texto}")
            self.bloqueo.boton.setEnabled(True)
            return
        self.bloqueo.mensaje(texto + "  Reiniciando...")
        QTimer.singleShot(1200, self._reiniciar)

    def abrir_asistente(self):
        if self.update_bloqueante or self.actualizando:
            return  # primero la actualizacion obligatoria; el asistente sale al volver a abrir
        from lumen.gui.asistente import Asistente

        asistente = Asistente(self)
        asistente.exec_()
        if asistente.crear_acceso.isVisible() and asistente.crear_acceso.isChecked():
            self.crear_acceso(silencioso=True)
        config.guardar({"acceso_ofrecido": True})
        self.paginas["personajes"].al_mostrar()
        self.navegar("inicio")

    def ofrecer_acceso(self):
        """Una sola vez, a quien ya tenia el bot antes de que existieran los accesos directos."""
        config.guardar({"acceso_ofrecido": True})
        if self.update_bloqueante or accesos.existen():
            return
        r = QMessageBox.question(self, "Acceso directo",
                                 "¿Creo un acceso directo a Lumen Farm en el escritorio y en el menú Inicio?\n\n"
                                 "Así lo abres con doble clic, con su icono, sin buscar la carpeta.")
        if r == QMessageBox.Yes:
            self.crear_acceso()

    def crear_acceso(self, silencioso: bool = False):
        try:
            accesos.crear()
        except Exception as error:
            QMessageBox.warning(self, "Acceso directo", f"No pude crear el acceso directo: {error}")
            return
        if not silencioso:
            QMessageBox.information(self, "Acceso directo",
                                    "Listo: tienes \"Lumen Farm\" en el escritorio y en el menú Inicio.")

    def _reiniciar(self):
        QProcess.startDetached(sys.executable, [str(RAIZ / "LumenFarm.pyw")], str(RAIZ))
        QApplication.quit()

    def closeEvent(self, evento):
        if self.puente.corriendo:
            r = QMessageBox.question(self, "Cerrar", "El bot esta farmeando. ¿Detenerlo y cerrar?")
            if r != QMessageBox.Yes:
                evento.ignore()
                return
            control.detener()
            self.puente.hilo.join(timeout=3)
        evento.accept()

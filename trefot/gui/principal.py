"""Ventana principal: menu lateral con paginas, barra de estado y actualizaciones obligatorias."""

import sys
import threading

from PyQt5.QtCore import QObject, QProcess, QSize, Qt, QTimer, pyqtSignal
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
    QVBoxLayout,
    QWidget,
)

import trefot
from trefot import actualizador, config, ventana
from trefot.control import control
from trefot.gui import iconos, tema
from trefot.gui.paginas.actualizaciones import PantallaBloqueo
from trefot.gui.paginas.ajustes import PaginaAjustes
from trefot.gui.paginas.ayuda import PaginaAyuda
from trefot.gui.paginas.capturas import PaginaCapturas
from trefot.gui.paginas.editor_personajes import PaginaEditorPersonajes
from trefot.gui.paginas.farmear import PaginaFarmear
from trefot.gui.paginas.historial import PaginaHistorial
from trefot.gui.paginas.equipos import PaginaEquipos
from trefot.gui.paginas.inicio import PaginaInicio
from trefot.gui.paginas.personajes import PaginaPersonajes
from trefot.gui.paginas.recompensas import PaginaRecompensas
from trefot.gui.puente import Puente
from trefot.modos import MODOS
from trefot.rutas import RAIZ

MINUTOS_ENTRE_REVISIONES = 30

MENU = [
    ("inicio", "Inicio"),
    ("farmear", "Farmear"),
    ("personajes", "Personajes"),
    ("equipos", "Equipos"),
    ("recompensas", "Recompensas"),
    ("historial", "Historial"),
    ("ayuda", "Ayuda"),
    ("ajustes", "Ajustes"),
    # Solo con el modo administrador (Ajustes): herramientas para mantener la base del bot.
    ("capturas", "Capturas"),
    ("editor", "Editor de personajes"),
]
SOLO_ADMIN = {"capturas", "editor"}


class _Senales(QObject):
    revision = pyqtSignal(object)  # actualizador.Estado
    progreso = pyqtSignal(str)
    fin_update = pyqtSignal(bool, str)


class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.version_cargada = trefot.__version__  # la que esta corriendo (la del disco puede ser mas nueva)
        self.setWindowTitle(f"TrefotFarm v{self.version_cargada}")
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
        lateral.setFixedWidth(210)
        capa_lat = QVBoxLayout(lateral)
        capa_lat.setContentsMargins(10, 14, 10, 12)
        capa_lat.addWidget(QLabel("Trefot Farm", objectName="marca"))
        capa_lat.addWidget(QLabel("AUTOFARMING · 7DS", objectName="lema"))
        capa_lat.addSpacing(8)
        capa_lat.addWidget(QFrame(objectName="separador_oro"))
        if tema.SKIN.saludo:
            saludo = QFrame(objectName="saludo")
            fila_s = QHBoxLayout(saludo)
            fila_s.setContentsMargins(8, 6, 8, 6)
            adorno = QLabel()
            adorno.setPixmap(iconos.pixmap(tema.SKIN.icono, 22, tema.ACENTO))
            fila_s.addWidget(adorno)
            fila_s.addWidget(QLabel(tema.SKIN.saludo, wordWrap=True), 1)
            capa_lat.addSpacing(8)
            capa_lat.addWidget(saludo)
        capa_lat.addSpacing(12)
        self.grupo = QButtonGroup(self, exclusive=True)
        self.botones: dict[str, QPushButton] = {}
        self.insignias: dict[str, QLabel] = {}
        for clave, texto in MENU:
            fila_b = QHBoxLayout()
            b = QPushButton("  " + texto, objectName="menu", checkable=True)
            b.setIcon(iconos.icono("mdi6.database-edit" if clave == "editor" else clave, tema.TENUE, tema.ACENTO))
            b.setIconSize(QSize(20, 20))
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _, c=clave: self.navegar(c))
            self.grupo.addButton(b)
            self.botones[clave] = b
            insignia = QLabel(objectName="insignia")
            insignia.hide()
            self.insignias[clave] = insignia
            fila_b.addWidget(b, 1)
            fila_b.addWidget(insignia)
            capa_lat.addLayout(fila_b)
        capa_lat.addStretch()
        self.lbl_version = QLabel(objectName="tenue")
        capa_lat.addWidget(self.lbl_version)
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
            "equipos": PaginaEquipos(self),
            "historial": PaginaHistorial(self),
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
        self.navegar("inicio")
        self.refrescar_insignias()
        self.aplicar_modo_admin()
        self._barra()
        self.farmear.escribir("TrefotFarm listo.", "ok")
        QTimer.singleShot(300, self.buscar_updates)
        if not config.obtener("asistente_visto"):
            QTimer.singleShot(700, self.abrir_asistente)

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
        self.lbl_version.setText(f"v{version}")
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
        from trefot.gui.asistente import Asistente

        Asistente(self).exec_()
        self.paginas["personajes"].al_mostrar()
        self.navegar("inicio")

    def _reiniciar(self):
        QProcess.startDetached(sys.executable, [str(RAIZ / "TrefotFarm.pyw")], str(RAIZ))
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

"""Pagina Ajustes: juego, aspecto, teclas, avisos al movil, modo administrador y repositorio de actualizaciones."""

from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from trefot import actualizador, avisos, config
from trefot.gui import iconos, tema
from trefot.gui.comun import Pagina


def seccion(titulo: str, icono: str) -> tuple[QFrame, QVBoxLayout]:
    """Recuadro con un icono y un titulo arriba; el contenido va en el layout devuelto."""
    marco = QFrame(objectName="seccion")
    capa = QVBoxLayout(marco)
    capa.setContentsMargins(16, 12, 16, 14)
    capa.setSpacing(8)
    cabecera = QHBoxLayout()
    dibujo = QLabel()
    dibujo.setPixmap(iconos.pixmap(icono, 20, tema.ACENTO))
    cabecera.addWidget(dibujo)
    cabecera.addWidget(QLabel(titulo, objectName="titulo_seccion"), 1)
    capa.addLayout(cabecera)
    return marco, capa


def nota(texto: str) -> QLabel:
    return QLabel(texto, objectName="tenue", wordWrap=True)


class PaginaAjustes(Pagina):
    titulo = "Ajustes"
    subtitulo = "Se guardan en config.yaml y las actualizaciones no los tocan."

    def __init__(self, app):
        super().__init__()
        self.app = app
        rejilla = QGridLayout()
        rejilla.setSpacing(14)

        juego, c = seccion("Juego", "juego")
        f = QFormLayout()
        self.titulo_ventana = QLineEdit(config.obtener("titulo_ventana"))
        f.addRow("Título de la ventana", self.titulo_ventana)
        c.addLayout(f)
        c.addWidget(nota("Global: 7DS · Japón: グラクロ. Solo cámbialo si juegas en otro cliente."))
        b_asistente = QPushButton(" Ver el asistente de primera vez", objectName="chico")
        b_asistente.setIcon(iconos.icono("ayuda", tema.TEXTO))
        b_asistente.clicked.connect(self.app.abrir_asistente)
        b_acceso = QPushButton(" Crear acceso directo", objectName="chico")
        b_acceso.setIcon(iconos.icono("mdi6.monitor-arrow-down", tema.TEXTO))
        b_acceso.clicked.connect(lambda: self.app.crear_acceso())
        fila_a = QHBoxLayout()
        fila_a.addWidget(b_asistente)
        fila_a.addWidget(b_acceso)
        fila_a.addStretch()
        c.addLayout(fila_a)
        rejilla.addWidget(juego, 0, 0)

        aspecto, c = seccion("Aspecto", "aspecto")
        self.skin = QComboBox()
        self.skin.addItem(f"Automática según la fecha (hoy: {tema.skin_de_fecha().nombre})", "auto")
        for skin in tema.SKINS.values():
            self.skin.addItem(skin.nombre, skin.id)
        self.skin.setCurrentIndex(max(0, self.skin.findData(config.obtener("skin"))))
        f = QFormLayout()
        f.addRow("Skin", self.skin)
        c.addLayout(f)
        c.addWidget(nota("En automática, la interfaz se viste para Halloween, Navidad, Año Nuevo, San Valentín "
                         "y el aniversario del juego."))
        rejilla.addWidget(aspecto, 0, 1)

        teclas, c = seccion("Teclas rápidas", "teclado")
        f = QFormLayout()
        self.tecla_pausa = QLineEdit(config.obtener("tecla_pausa"))
        self.tecla_detener = QLineEdit(config.obtener("tecla_detener"))
        f.addRow("Pausar / reanudar", self.tecla_pausa)
        f.addRow("Detener", self.tecla_detener)
        c.addLayout(f)
        c.addWidget(nota("Funcionan aunque el juego esté al frente. Nombres como f9, f10, pause, end..."))
        rejilla.addWidget(teclas, 1, 0)

        movil, c = seccion("Avisos al móvil", "movil")
        f = QFormLayout()
        self.ntfy = QLineEdit()
        self.ntfy.setText(config.obtener("ntfy_canal"))
        self.ntfy.setPlaceholderText("vacío = sin avisos")
        self.atasco = QSpinBox(minimum=0, maximum=120, value=int(config.obtener("minutos_atasco")))
        self.atasco.setSuffix(" min")
        f.addRow("Canal de ntfy", self.ntfy)
        f.addRow("Avisar si se atasca (0 = no)", self.atasco)
        c.addLayout(f)
        self.ordenes = QCheckBox("Aceptar órdenes desde el móvil (escribe 'ayuda' en el canal)")
        self.ordenes.setChecked(bool(config.obtener("ntfy_ordenes")))
        c.addWidget(self.ordenes)
        fila = QHBoxLayout()
        fila.addWidget(nota("Instala la app gratuita ntfy y suscríbete a un canal con un nombre difícil de adivinar: "
                            "quien sepa el nombre puede leer los avisos y, con las órdenes activas, manejar el bot."), 1)
        b_probar = QPushButton(" Probar", objectName="chico")
        b_probar.setIcon(iconos.icono("movil", tema.TEXTO))
        b_probar.clicked.connect(self.probar)
        fila.addWidget(b_probar)
        c.addLayout(fila)
        rejilla.addWidget(movil, 1, 1)

        repo, c = seccion("Actualizaciones", "actualizar")
        f = QFormLayout()
        self.url_repo = QLineEdit(placeholderText="https://github.com/usuario/TrefotFarm.git")
        self.url_repo.setText(actualizador.url_remota())
        f.addRow("Repositorio", self.url_repo)
        c.addLayout(f)
        c.addWidget(nota("De aquí se bajan las actualizaciones obligatorias. Solo cámbialo si mueves el repositorio."))
        rejilla.addWidget(repo, 2, 0)

        admin, c = seccion("Administrador", "admin")
        self.modo_admin = QCheckBox("Modo administrador: mostrar Capturas y el Editor de personajes")
        self.modo_admin.setChecked(bool(config.obtener("modo_admin")))
        c.addWidget(self.modo_admin)
        c.addWidget(nota("Solo para quien mantiene la base del bot (cartas, retratos y equipos). "
                         "Los jugadores normales no lo necesitan."))
        rejilla.addWidget(admin, 2, 1)
        rejilla.setColumnStretch(0, 1)
        rejilla.setColumnStretch(1, 1)
        self.cuerpo.addLayout(rejilla)

        botones = QHBoxLayout()
        b_guardar = QPushButton(" Guardar cambios", objectName="primario")
        b_guardar.setIcon(iconos.icono("guardar", tema.SOBRE_ACENTO))
        b_guardar.setIconSize(QSize(18, 18))
        b_guardar.setMinimumHeight(40)
        b_guardar.clicked.connect(self.guardar)
        botones.addWidget(b_guardar)
        botones.addStretch()
        self.cuerpo.addLayout(botones)
        self.cuerpo.addStretch()

    def guardar(self, silencioso=False):
        skin_cambiada = self.skin.currentData() != config.obtener("skin")
        config.guardar({
            "skin": self.skin.currentData(),
            "titulo_ventana": self.titulo_ventana.text().strip() or "7DS",
            "ntfy_canal": self.ntfy.text().strip(),
            "ntfy_ordenes": self.ordenes.isChecked(),
            "minutos_atasco": self.atasco.value(),
            "tecla_pausa": self.tecla_pausa.text().strip().lower() or "f9",
            "tecla_detener": self.tecla_detener.text().strip().lower() or "f10",
            "modo_admin": self.modo_admin.isChecked(),
        })
        url = self.url_repo.text().strip()
        if url and url != actualizador.url_remota():
            try:
                actualizador.configurar_remoto(url)
            except actualizador.ErrorActualizacion as e:
                QMessageBox.warning(self, "Repositorio", f"No pude guardar el repositorio: {e}")
                return
            self.app.buscar_updates(manual=True)
        self.app.ajustes_guardados()
        if skin_cambiada and not self.app.puente.corriendo:
            r = QMessageBox.question(self, "Skin", "La skin nueva se ve al reiniciar TrefotFarm. ¿Reiniciar ahora?")
            if r == QMessageBox.Yes:
                self.app._reiniciar()
                return
        if not silencioso:
            QMessageBox.information(self, "Ajustes", "Guardado.")

    def probar(self):
        self.guardar(silencioso=True)
        if not config.obtener("ntfy_canal"):
            QMessageBox.information(self, "Avisos", "Escribe primero un canal.")
            return
        avisos.enviar("TrefotFarm: aviso de prueba")
        QMessageBox.information(self, "Avisos", "Enviado. Debería llegarte en unos segundos.")

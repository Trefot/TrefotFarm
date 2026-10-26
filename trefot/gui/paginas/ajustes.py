"""Pagina Ajustes: ventana del juego, avisos al movil, teclas, vista previa y repositorio de actualizaciones."""

from PyQt5.QtWidgets import QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox

from trefot import actualizador, avisos, config
from trefot.gui.comun import Pagina


class PaginaAjustes(Pagina):
    titulo = "Ajustes"
    subtitulo = "Se guardan en config.yaml y las actualizaciones no los tocan."

    def __init__(self, app):
        super().__init__()
        self.app = app
        fila = QHBoxLayout()

        juego = QGroupBox("Juego")
        f1 = QFormLayout(juego)
        self.titulo_ventana = QLineEdit(config.obtener("titulo_ventana"))
        f1.addRow("Titulo de la ventana", self.titulo_ventana)
        f1.addRow(QLabel("Global: 7DS · Japon: グラクロ", objectName="tenue"))
        self.fps = QSpinBox(minimum=1, maximum=10, value=int(config.obtener("fps_vista_previa")))
        f1.addRow("Vista previa (fotos/seg)", self.fps)
        fila.addWidget(juego)

        controles = QGroupBox("Teclas rapidas")
        f2 = QFormLayout(controles)
        self.tecla_pausa = QLineEdit(config.obtener("tecla_pausa"))
        self.tecla_detener = QLineEdit(config.obtener("tecla_detener"))
        f2.addRow("Pausar / reanudar", self.tecla_pausa)
        f2.addRow("Detener", self.tecla_detener)
        f2.addRow(QLabel("Nombres como f9, f10, pause, end...", objectName="tenue"))
        fila.addWidget(controles)
        self.cuerpo.addLayout(fila)

        movil = QGroupBox("Avisos al movil (ntfy)")
        f3 = QFormLayout(movil)
        self.ntfy = QLineEdit(config.obtener("ntfy_canal"))
        self.ntfy.setPlaceholderText("vacio = sin avisos")
        self.atasco = QSpinBox(minimum=0, maximum=120, value=int(config.obtener("minutos_atasco")))
        f3.addRow("Canal", self.ntfy)
        f3.addRow("Avisar si se atasca (min, 0 = no)", self.atasco)
        f3.addRow(QLabel("Instala la app gratuita ntfy y suscribete a un canal con un nombre dificil de adivinar.",
                         objectName="tenue", wordWrap=True))
        self.cuerpo.addWidget(movil)

        repo = QGroupBox("Actualizaciones (GitHub)")
        f4 = QFormLayout(repo)
        self.url_repo = QLineEdit(placeholderText="https://github.com/usuario/TrefotFarm.git")
        self.url_repo.setText(actualizador.url_remota())
        f4.addRow("Repositorio", self.url_repo)
        f4.addRow(QLabel("De aqui se bajan las actualizaciones obligatorias. Solo cambialo si mueves el repositorio.",
                         objectName="tenue", wordWrap=True))
        self.cuerpo.addWidget(repo)

        botones = QHBoxLayout()
        b_guardar = QPushButton("Guardar", objectName="primario")
        b_guardar.clicked.connect(self.guardar)
        b_probar = QPushButton("Probar aviso al movil")
        b_probar.clicked.connect(self.probar)
        botones.addWidget(b_guardar)
        botones.addWidget(b_probar)
        botones.addStretch()
        self.cuerpo.addLayout(botones)
        self.cuerpo.addStretch()

    def guardar(self, silencioso=False):
        config.guardar({
            "titulo_ventana": self.titulo_ventana.text().strip() or "7DS",
            "ntfy_canal": self.ntfy.text().strip(),
            "minutos_atasco": self.atasco.value(),
            "tecla_pausa": self.tecla_pausa.text().strip().lower() or "f9",
            "tecla_detener": self.tecla_detener.text().strip().lower() or "f10",
            "fps_vista_previa": self.fps.value(),
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
        if not silencioso:
            QMessageBox.information(self, "Ajustes", "Guardado.")

    def probar(self):
        self.guardar(silencioso=True)
        if not config.obtener("ntfy_canal"):
            QMessageBox.information(self, "Avisos", "Escribe primero un canal.")
            return
        avisos.enviar("TrefotFarm: aviso de prueba")
        QMessageBox.information(self, "Avisos", "Enviado. Deberia llegarte en unos segundos.")

"""Aviso de Inicio con los heroes recien llegados al juego (de 7dshub): cada jugador dice si lo tiene o no y el heroe
se va del aviso y queda en su galeria de Personajes segun su respuesta (el usuario, 2026-11-13)."""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from lumen import personajes as P
from lumen.gui import tema

TAM_ICONO = 64


class FilaHeroe(QFrame):
    def __init__(self, pj: P.Personaje, responder):
        super().__init__(objectName="contenido_card")
        capa = QHBoxLayout(self)
        capa.setContentsMargins(10, 8, 10, 8)
        icono = QLabel(alignment=Qt.AlignCenter)
        icono.setFixedSize(TAM_ICONO, TAM_ICONO)
        ruta = pj.ruta_cara()
        if ruta.is_file():
            icono.setPixmap(QPixmap(str(ruta)).scaled(TAM_ICONO, TAM_ICONO, Qt.KeepAspectRatio,
                                                       Qt.SmoothTransformation))
        capa.addWidget(icono)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        clave = (P._leer_yaml(P.BASE).get(pj.id) or {}).get("clave") or pj.nombre
        nombre = QLabel(clave, objectName="titulo_seccion", wordWrap=True)
        nombre.setTextFormat(Qt.PlainText)
        textos.addWidget(nombre)
        textos.addWidget(QLabel(f"Atributo {pj.color} · ¿Lo tienes?", objectName="tenue"))
        capa.addLayout(textos, 1)
        si = QPushButton("Lo tengo", objectName="primario")
        si.clicked.connect(lambda: responder(pj.id, True))
        no = QPushButton("No lo tengo", objectName="chico")
        no.clicked.connect(lambda: responder(pj.id, False))
        capa.addWidget(si)
        capa.addWidget(no)


class PanelHeroesNuevos(QFrame):
    """Se esconde solo cuando no queda ningun heroe nuevo por responder."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent, objectName="seccion")
        capa = QVBoxLayout(self)
        capa.setContentsMargins(16, 12, 16, 12)
        capa.setSpacing(8)
        capa.addWidget(QLabel("¡Héroes nuevos en el juego!", objectName="titulo_seccion"))
        nota = QLabel("Dime si ya los tienes: se guardan en tu galería de Personajes y el bot sabrá si puede usarlos.",
                      objectName="tenue", wordWrap=True)
        capa.addWidget(nota)
        self.lista = QVBoxLayout()
        self.lista.setSpacing(6)
        capa.addLayout(self.lista)
        self._mostrados: list[str] = []
        self.refrescar()

    def refrescar(self):
        try:
            pids = P.nuevos_sin_responder()
            biblioteca = P.cargar() if pids else {}
        except Exception:  # nunca romper Inicio por esto
            pids, biblioteca = [], {}
        pids = [pid for pid in pids if pid in biblioteca]
        if pids == self._mostrados:
            self.setVisible(bool(pids))
            return
        while self.lista.count():
            w = self.lista.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        for pid in pids:
            self.lista.addWidget(FilaHeroe(biblioteca[pid], self._responder))
        self._mostrados = pids
        self.setVisible(bool(pids))

    def _responder(self, pid: str, tengo: bool):
        P.marcar_tengo(pid, tengo)
        self.refrescar()

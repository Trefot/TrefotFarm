"""Pagina Equipos: para cada contenido, que equipo necesitas, si lo tienes y con quien sustituir."""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from trefot import armador
from trefot import personajes as P
from trefot.gui import tema
from trefot.gui.comun import Pagina
from trefot.modos import MODOS

FALTAN_CAPTURAS = "faltan_capturas"
ESTADO = {
    armador.LISTO: ("✔ Listo para farmear", tema.OK),
    FALTAN_CAPTURAS: ("◐ Tienes el equipo; faltan capturas", tema.AVISO),
    armador.CON_SUSTITUTOS: ("◐ Posible con sustitutos (a mano)", tema.AVISO),
    armador.INCOMPLETO: ("✖ Te faltan personajes", tema.ERROR),
}


class PaginaEquipos(Pagina):
    titulo = "Equipos"
    subtitulo = (
        "Que equipo pide cada contenido y si lo puedes armar con los personajes que tienes. "
        "Marca los tuyos y sus roles en la pagina Personajes."
    )

    def __init__(self, app):
        super().__init__()
        self.app = app
        fila = QHBoxLayout()

        izq = QVBoxLayout()
        izq.addWidget(QLabel("<b>Contenidos</b>"))
        self.lista = QListWidget()
        self.lista.currentItemChanged.connect(lambda item, _: self._mostrar(item.data(Qt.UserRole) if item else None))
        izq.addWidget(self.lista)
        contenedor = QWidget()
        contenedor.setLayout(izq)
        contenedor.setFixedWidth(300)
        fila.addWidget(contenedor)

        der = QVBoxLayout()
        self.titulo_modo = QLabel(objectName="cifra")
        self.estado = QLabel()
        der.addWidget(self.titulo_modo)
        der.addWidget(self.estado)

        grupo = QGroupBox("Puestos (izquierda a derecha en la pantalla del equipo)")
        capa = QVBoxLayout(grupo)
        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(["#", "Funcion", "Recomendado", "¿Lo tienes?", "Sustitutos tuyos"])
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setSelectionMode(QAbstractItemView.NoSelection)
        self.tabla.setWordWrap(True)
        cab = self.tabla.horizontalHeader()
        cab.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        cab.setSectionResizeMode(1, QHeaderView.Stretch)
        cab.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        cab.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        cab.setSectionResizeMode(4, QHeaderView.Stretch)
        capa.addWidget(self.tabla)
        der.addWidget(grupo, 1)

        self.capturas = QLabel(wordWrap=True)
        der.addWidget(self.capturas)

        nota = QFrame(objectName="aviso")
        capa_nota = QHBoxLayout(nota)
        capa_nota.addWidget(QLabel(
            "El bot solo juega el guion con el equipo <b>recomendado</b>. Los sustitutos te sirven para jugar a mano "
            "o como punto de partida de un guion nuevo.", wordWrap=True), 1)
        der.addWidget(nota)

        botones = QHBoxLayout()
        b_pj = QPushButton("Ir a Personajes")
        b_pj.clicked.connect(lambda: app.navegar("personajes"))
        b_cap = QPushButton("Ir a Capturas")
        b_cap.clicked.connect(lambda: app.navegar("capturas"))
        botones.addWidget(b_pj)
        botones.addWidget(b_cap)
        botones.addStretch()
        der.addLayout(botones)

        fila.addLayout(der, 1)
        self.cuerpo.addLayout(fila, 1)
        self.al_mostrar()

    def al_mostrar(self):
        self.biblioteca = P.cargar()
        actual = self.lista.currentItem().data(Qt.UserRole) if self.lista.currentItem() else None
        self.lista.blockSignals(True)
        self.lista.clear()
        for modo in MODOS.values():
            if not getattr(modo, "equipo", None):
                continue
            texto, color = ESTADO[self._estado(modo)]
            item = QListWidgetItem(f"{modo.nombre}\n{texto}")
            item.setForeground(QColor(color))
            item.setData(Qt.UserRole, modo.id)
            self.lista.addItem(item)
        self.lista.blockSignals(False)
        fila = next((i for i in range(self.lista.count()) if self.lista.item(i).data(Qt.UserRole) == actual), 0)
        if self.lista.count():
            self.lista.setCurrentRow(fila)
            self._mostrar(self.lista.item(fila).data(Qt.UserRole))

    def _estado(self, modo, analisis=None) -> str:
        """El estado del armador, pero 'listo' solo si ademas estan todas las capturas obligatorias."""
        estado = (analisis or armador.analizar(modo.equipo, self.biblioteca)).estado
        if estado == armador.LISTO and modo.equipo.faltantes():
            return FALTAN_CAPTURAS
        return estado

    def _mostrar(self, id_modo: str | None):
        if not id_modo:
            return
        modo = MODOS[id_modo]
        modo.equipo.recargar()
        analisis = armador.analizar(modo.equipo, self.biblioteca)
        self.titulo_modo.setText(modo.nombre)
        texto, color = ESTADO[self._estado(modo, analisis)]
        self.estado.setText(f"<span style='color:{color}'><b>{texto}</b></span>")

        self.tabla.setRowCount(len(analisis.puestos))
        for fila, a in enumerate(analisis.puestos):
            roles = ", ".join(P.ROLES.get(r, r) for r in a.puesto.roles)
            if a.lo_tienes:
                sustitutos = "—"
            elif a.sustitutos:
                sustitutos = ", ".join(pj.nombre + (" (sugerido)" if pj is a.elegido else "") for pj in a.sustitutos)
            else:
                sustitutos = "ninguno de tus personajes tiene esos roles"
            celdas = [
                (str(fila + 1), None),
                (f"{a.puesto.funcion}\nRoles: {roles}", None),
                (a.recomendado.nombre if a.recomendado else a.puesto.recomendado, None),
                ("✔ si" if a.lo_tienes else "✖ no", tema.OK if a.lo_tienes else tema.ERROR),
                (sustitutos, tema.TENUE if a.lo_tienes else None),
            ]
            for col, (valor, color_celda) in enumerate(celdas):
                item = QTableWidgetItem(valor)
                if color_celda:
                    item.setForeground(QColor(color_celda))
                self.tabla.setItem(fila, col, item)
        self.tabla.resizeRowsToContents()

        estado_cartas = modo.equipo.estado()
        listas = sum(1 for d, e in estado_cartas if e != "falta")
        faltan = modo.equipo.faltantes()
        sin_retrato = [pid for pid in modo.equipo.orden if pid in self.biblioteca and not self.biblioteca[pid].tiene_captura(P.RETRATO)]
        partes = [f"Cartas listas: {listas}/{len(estado_cartas)}"]
        if faltan:
            partes.append(f"<span style='color:{tema.ERROR}'>obligatorias que faltan: {len(faltan)}</span>")
        if sin_retrato:
            nombres = ", ".join(self.biblioteca[p].nombre for p in sin_retrato)
            partes.append(f"<span style='color:{tema.AVISO}'>sin retrato (no se puede comprobar el equipo): {nombres}</span>")
        self.capturas.setText(" · ".join(partes))

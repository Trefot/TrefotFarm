"""Plan del dia: una lista de tareas (modo + victorias) que el bot hace una tras otra sin nadie.

Se guarda en config.yaml ("plan": [{"modo": id, "victorias": n}, ...]; victorias 0 = hasta completar
las metas de material que da ese modo, ver lumen/metas.py). La pagina Farmear lo ejecuta:
al terminar una tarea arranca la siguiente; si se detiene a mano (boton o F10), el plan se para.
"""

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout

from lumen import config
from lumen.gui import iconos, tema
from lumen.modos import MODOS
from lumen.modos.catalogo import foto_de

VICTORIAS_DEFECTO = 10
META = "🎯 Meta"  # victorias 0 en una tarea: farmear hasta completar las metas que da ese modo
AYUDA_META = "Baja hasta «🎯 Meta» para farmear hasta completar tus metas de ese material"


def texto_victorias(victorias: int) -> str:
    return "hasta completar sus metas" if int(victorias) == 0 else f"{victorias} victorias"


def _spin(valor: int, sufijo: str) -> QSpinBox:
    spin = QSpinBox(minimum=0, maximum=999, value=valor, suffix=sufijo)
    spin.setSpecialValueText(META)
    spin.setToolTip(AYUDA_META)
    return spin


def cargar() -> list[dict]:
    """Las tareas del plan que se pueden jugar (las de modos que ya no existen se saltan)."""
    return [t for t in (config.obtener("plan") or []) if t.get("modo") in MODOS]


def guardar(tareas: list[dict]) -> None:
    config.guardar({"plan": [{"modo": t["modo"], "victorias": int(t["victorias"])} for t in tareas]})


class PanelPlan(QFrame):
    """La lista editable de tareas y el boton para lanzar el plan."""

    iniciar = pyqtSignal()
    saltar = pyqtSignal()
    probar = pyqtSignal()

    def __init__(self):
        super().__init__(objectName="seccion")
        capa = QVBoxLayout(self)
        capa.setSpacing(6)
        capa.addWidget(QLabel("El bot hace las tareas en orden. Al acabar una, empieza la siguiente.",
                              objectName="tenue", wordWrap=True))
        self.lista = QVBoxLayout()
        self.lista.setSpacing(4)
        capa.addLayout(self.lista)

        nueva = QHBoxLayout()
        self.combo = QComboBox()
        for modo in MODOS.values():
            self.combo.addItem(modo.nombre, modo.id)
        nueva.addWidget(self.combo, 1)
        self.spin = _spin(VICTORIAS_DEFECTO, " victorias")
        nueva.addWidget(self.spin)
        b_anadir = QPushButton(" Añadir", objectName="chico")
        b_anadir.setIcon(iconos.icono("mdi6.plus", tema.TEXTO))
        b_anadir.clicked.connect(self._anadir)
        nueva.addWidget(b_anadir)
        capa.addLayout(nueva)
        capa.addStretch()

        fila = QHBoxLayout()
        self.lbl_estado = QLabel(objectName="tenue")
        fila.addWidget(self.lbl_estado, 1)
        self.b_probar = QPushButton(" Prueba rápida")
        self.b_probar.setIcon(iconos.icono("mdi6.clipboard-check-outline", tema.TEXTO))
        self.b_probar.setToolTip("1 victoria de cada modo listo y un informe de lo que funcionó")
        self.b_probar.clicked.connect(self.probar.emit)
        fila.addWidget(self.b_probar)
        self.b_saltar = QPushButton(" Saltar tarea")
        self.b_saltar.setIcon(iconos.icono("mdi6.skip-next", tema.TEXTO))
        self.b_saltar.setToolTip("Deja la tarea en curso y pasa a la siguiente")
        self.b_saltar.clicked.connect(self.saltar.emit)
        fila.addWidget(self.b_saltar)
        self.b_iniciar = QPushButton(" Iniciar plan", objectName="primario")
        self.b_iniciar.setIcon(iconos.icono("jugar", tema.SOBRE_ACENTO))
        self.b_iniciar.clicked.connect(self.iniciar.emit)
        fila.addWidget(self.b_iniciar)
        capa.addLayout(fila)
        self.actual: int | None = None
        self.pintar()

    # ------------------------------------------------------------------ editar
    def _anadir(self):
        tareas = cargar()
        tareas.append({"modo": self.combo.currentData(), "victorias": self.spin.value()})
        guardar(tareas)
        self.pintar()

    def _cambiar(self, i: int, victorias: int):
        tareas = cargar()
        tareas[i]["victorias"] = victorias
        guardar(tareas)

    def _mover(self, i: int, paso: int):
        tareas = cargar()
        j = i + paso
        if 0 <= j < len(tareas):
            tareas[i], tareas[j] = tareas[j], tareas[i]
            guardar(tareas)
            self.pintar()

    def _quitar(self, i: int):
        tareas = cargar()
        tareas.pop(i)
        guardar(tareas)
        self.pintar()

    # ------------------------------------------------------------------ dibujar
    def marcar(self, actual: int | None):
        """La tarea en curso (o None si el plan no esta en marcha)."""
        self.actual = actual
        self.pintar()

    def pintar(self):
        while self.lista.count():
            w = self.lista.takeAt(0).widget()
            if w:
                w.setParent(None)
        tareas = cargar()
        en_marcha = self.actual is not None
        for i, t in enumerate(tareas):
            fila = QFrame(objectName="tarea_plan")
            fila.setProperty("estado", "actual" if i == self.actual else "hecha" if en_marcha and i < self.actual else "")
            capa = QHBoxLayout(fila)
            capa.setContentsMargins(6, 4, 4, 4)
            capa.addWidget(QLabel(f"{i + 1}.", objectName="tenue"))
            foto = QLabel()
            pix = iconos.redondo(foto_de(t["modo"]), 30, tema.ACENTO) if foto_de(t["modo"]) else None
            if pix:
                foto.setPixmap(pix)
            capa.addWidget(foto)
            capa.addWidget(QLabel(MODOS[t["modo"]].nombre), 1)
            spin = _spin(int(t["victorias"]), " vict.")
            spin.setEnabled(not en_marcha)
            spin.valueChanged.connect(lambda v, n=i: self._cambiar(n, v))
            capa.addWidget(spin)
            for icono, ayuda, accion in (("mdi6.arrow-up", "Subir", lambda _=False, n=i: self._mover(n, -1)),
                                         ("mdi6.arrow-down", "Bajar", lambda _=False, n=i: self._mover(n, 1)),
                                         ("mdi6.close", "Quitar", lambda _=False, n=i: self._quitar(n))):
                b = QPushButton(objectName="chico")
                b.setFlat(True)
                b.setIcon(iconos.icono(icono, tema.TEXTO))
                b.setIconSize(QSize(16, 16))
                b.setToolTip(ayuda)
                b.setEnabled(not en_marcha)
                b.clicked.connect(accion)
                capa.addWidget(b)
            self.lista.addWidget(fila)
        if not tareas:
            self.lista.addWidget(QLabel("Aún no hay tareas: elige un modo abajo y pulsa Añadir.", objectName="tenue"))
        total = sum(int(t["victorias"]) for t in tareas)
        con_meta = sum(1 for t in tareas if int(t["victorias"]) == 0)
        if en_marcha:
            self.lbl_estado.setText(f"En marcha: tarea {self.actual + 1} de {len(tareas)}")
        else:
            partes = [f"{len(tareas)} tarea{'s' if len(tareas) != 1 else ''}"] + ([f"{total} victorias"] if total else []) \
                + ([f"{con_meta} hasta la meta"] if con_meta else [])
            self.lbl_estado.setText(" · ".join(partes) if tareas else "")
        self.b_iniciar.setEnabled(bool(tareas) and not en_marcha)
        self.b_saltar.setVisible(en_marcha)
        self.b_probar.setVisible(not en_marcha)
        self.combo.setEnabled(not en_marcha)

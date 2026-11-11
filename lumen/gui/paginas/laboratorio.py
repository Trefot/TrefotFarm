"""Diagnostico y memoria reversibles, reservados al administrador."""

from PyQt5.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QMessageBox,
    QFileDialog,
)

from lumen import admin
from lumen.gui.comun import Pagina
from lumen.ia import perfiles, cobertura, evaluacion, equipos as equipos_ia
from lumen.modos import MODOS


class PaginaLaboratorio(Pagina):
    titulo = "Laboratorio"
    subtitulo = "Administración · comparación, memoria y conocimiento 7DS"

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.panel = app.farmear.reproductor
        fila = QHBoxLayout()
        fila.addWidget(QLabel("Contexto del análisis"))
        self.modo = QComboBox()
        for clave, modo in MODOS.items():
            self.modo.addItem(modo.nombre, clave)
        self.modo.setCurrentIndex(max(0, self.modo.findData(app.farmear.modo_cls.id)))
        fila.addWidget(self.modo, 1)
        fila.addWidget(QLabel("Nivel de demonio"))
        self.nivel = QComboBox()
        self.nivel.addItems(["Chaos", "Hell", "Extreme", "Hard", "Normal"])
        fila.addWidget(self.nivel)
        self.cuerpo.addLayout(fila)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.panel, "Capturas y comparación")
        memoria = QWidget()
        capa = QVBoxLayout(memoria)
        capa.addWidget(
            QLabel(
                "La memoria usa el destino, piso/fase y equipo indicados en Capturas. Sin un equipo completo no se modifica nada.",
                wordWrap=True,
            )
        )
        self.memoria_texto = QTextEdit(readOnly=True)
        capa.addWidget(self.memoria_texto, 1)
        self.copias = QComboBox()
        capa.addWidget(self.copias)
        botones = QHBoxLayout()
        for texto, fn in (
            ("Ver memoria", self.ver_memoria),
            ("Guardar copia", self.guardar),
            ("Restaurar copia", self.restaurar),
            ("Volver a la base", self.reiniciar),
        ):
            boton = QPushButton(texto)
            boton.clicked.connect(fn)
            botones.addWidget(boton)
        capa.addLayout(botones)
        self.tabs.addTab(memoria, "Memoria")
        conocimiento = QWidget()
        capa_c = QVBoxLayout(conocimiento)
        self.conocimiento = QTextEdit(readOnly=True)
        capa_c.addWidget(self.conocimiento, 1)
        revisar = QPushButton("Revisar conocimiento incluido")
        revisar.clicked.connect(self.ver_conocimiento)
        capa_c.addWidget(revisar)
        self.tabs.addTab(conocimiento, "Conocimiento 7DS")
        self.diarios_importados = None
        validacion = QWidget()
        capa_v = QVBoxLayout(validacion)
        capa_v.addWidget(
            QLabel(
                "Evaluar no modifica la memoria. Selecciona el destino y equipo en Capturas.",
                wordWrap=True,
            )
        )
        self.evaluacion_texto = QTextEdit(readOnly=True)
        capa_v.addWidget(self.evaluacion_texto, 1)
        botones_v = QHBoxLayout()
        for texto, fn in (
            ("Evaluar diarios locales", self.evaluar_local),
            ("Abrir diario JSONL", self.importar_diario),
            ("Evaluar diario abierto", self.evaluar_importado),
            ("Recomendar equipos registrados", self.recomendar),
        ):
            boton = QPushButton(texto)
            boton.clicked.connect(fn)
            botones_v.addWidget(boton)
        capa_v.addLayout(botones_v)
        self.tabs.addTab(validacion, "Validación y equipos")
        self.cuerpo.addWidget(self.tabs, 1)
        self.panel.contexto = self.contexto
        self.modo.currentIndexChanged.connect(self._cambiar_contexto)
        self.nivel.currentIndexChanged.connect(lambda: self._limpiar_memoria())
        self.panel.equipo.textChanged.connect(lambda: self._limpiar_memoria())
        self.panel.piso.valueChanged.connect(lambda: self._limpiar_memoria())

    def _cambiar_contexto(self):
        self.nivel.setEnabled(self.contexto()[1])
        self._limpiar_memoria()

    def contexto(self):
        clave = self.modo.currentData()
        demonios = {
            "indura",
            "demonio_rojo",
            "demonio_gris",
            "howlex",
            "bellmoth",
            "demonio_original",
        }
        es_demonio = clave in demonios
        return (
            f"{clave}_{self.nivel.currentText().lower()}" if es_demonio else clave
        ), es_demonio

    def _datos(self):
        admin.exigir()
        destino, _ = self.contexto()
        if destino.endswith("_pisos1a3"):
            destino = destino.replace("_pisos1a3", f"_f{self.panel.piso.value()}")
        equipo = [p.strip() for p in self.panel.equipo.text().split(",") if p.strip()]
        if not perfiles.equipo_clave(equipo):
            raise ValueError(
                "Indica los IDs de 3 o 4 héroes distintos en Capturas para elegir la memoria."
            )
        return destino, equipo

    def _ocupado(self):
        return (
            self.panel.ocupado
            or self.app.puente.corriendo
            or self.app.farmear.plan_paso is not None
        )

    def _limpiar_memoria(self):
        self.memoria_texto.clear()
        self.copias.clear()

    def ver_memoria(self):
        try:
            destino, equipo = self._datos()
            datos = perfiles.estado(destino, equipo)
            from lumen.ia import lecciones, aprendizaje

            texto = lecciones.resumen(destino, perfiles.carpeta(destino, equipo))
            self.memoria_texto.setPlainText(
                f"{destino}\nEquipo: {', '.join(equipo)}\n\n{texto}\n\nPolítica: {aprendizaje.diferencia(perfiles.parametros(destino, equipo)) or 'parámetros base'}\n"
                + (
                    "Recuperación incompleta: memoria suspendida."
                    if datos.get("perfil", {}).get("restaurando")
                    else ""
                )
            )
            self.copias.clear()
            self.copias.addItems(perfiles.copias(destino, equipo))
        except Exception as error:
            self.memoria_texto.setPlainText(str(error))

    def guardar(self):
        try:
            destino, equipo = self._datos()
            perfiles.guardar_copia(destino, equipo, ocupado=self._ocupado())
            self.ver_memoria()
        except Exception as error:
            self.memoria_texto.setPlainText(str(error))

    def _restaurar(self, nombre):
        try:
            destino, equipo = self._datos()
            if self._ocupado():
                raise RuntimeError(
                    "Detén el bot, el plan y el análisis antes de restaurar."
                )
            if (
                QMessageBox.question(
                    self,
                    "Restaurar aprendizaje",
                    "Se guardará una copia del estado actual antes de cambiarlo. ¿Continuar?",
                )
                != QMessageBox.Yes
            ):
                return
            perfiles.restaurar(destino, equipo, nombre, ocupado=self._ocupado())
            self.ver_memoria()
        except Exception as error:
            self.memoria_texto.setPlainText(str(error))

    def restaurar(self):
        if not self.copias.currentText():
            self.memoria_texto.setPlainText("Selecciona una copia guardada.")
            return
        self._restaurar(self.copias.currentText())

    def reiniciar(self):
        self._restaurar(None)

    def ver_conocimiento(self):
        try:
            self.conocimiento.setPlainText(cobertura.informe())
        except Exception as error:
            self.conocimiento.setPlainText(str(error))

    def _registros_locales(self):
        admin.exigir()
        from lumen.ia import diario

        return diario.leer(limite=1000)

    def _evaluar(self, registros):
        destino, equipo = self._datos()
        informe = evaluacion.analizar(registros, destino, equipo)
        self.evaluacion_texto.setPlainText(evaluacion.texto(informe))

    def evaluar_local(self):
        try:
            self._evaluar(self._registros_locales())
        except Exception as error:
            self.evaluacion_texto.setPlainText(str(error))

    def importar_diario(self):
        try:
            admin.exigir()
            ruta, _ = QFileDialog.getOpenFileName(
                self, "Diario para evaluar (no entrena)", "", "Diarios (*.jsonl)"
            )
            if ruta:
                from pathlib import Path

                self.diarios_importados, invalidos = evaluacion.leer_archivo(Path(ruta))
                self.evaluacion_texto.setPlainText(
                    f"Registros abiertos: {len(self.diarios_importados)}; inválidos: {invalidos}. Pulsa Evaluar diario abierto."
                )
        except Exception as error:
            self.diarios_importados = None
            self.evaluacion_texto.setPlainText(str(error))

    def evaluar_importado(self):
        try:
            admin.exigir()
            if self.diarios_importados is None:
                raise ValueError("Abre primero un diario JSONL.")
            self._evaluar(self.diarios_importados)
        except Exception as error:
            self.evaluacion_texto.setPlainText(str(error))

    def recomendar(self):
        try:
            admin.exigir()
            from lumen import personajes
            from lumen.gui.paginas.equipos import cargar_equipos

            destino, _ = self.contexto()
            if destino.endswith("_pisos1a3"):
                destino = destino.replace("_pisos1a3", f"_f{self.panel.piso.value()}")
            recomendaciones = equipos_ia.recomendar(
                destino,
                personajes.cargar(),
                cargar_equipos(),
                self._registros_locales(),
            )
            self.evaluacion_texto.setPlainText(
                equipos_ia.texto(destino, recomendaciones)
            )
        except Exception as error:
            self.evaluacion_texto.setPlainText(str(error))

    def revocar(self):
        self.panel.revocar()
        self._limpiar_memoria()
        self.conocimiento.clear()
        self.evaluacion_texto.clear()
        self.diarios_importados = None

    def al_mostrar(self):
        admin.exigir()

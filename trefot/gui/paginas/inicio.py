"""Pagina Inicio: de un vistazo, si todo esta listo para farmear, y arranque rapido."""

import time

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout

from trefot import config, historial, ventana
from trefot.actualizador import version_local
from trefot.gui import tema
from trefot.gui.comun import Pagina, formatear_tiempo, tarjeta
from trefot.modos import MODOS


def _estado(titulo: str) -> tuple[QFrame, QLabel, QLabel, QHBoxLayout]:
    marco = QFrame(objectName="tarjeta")
    capa = QVBoxLayout(marco)
    capa.setContentsMargins(14, 10, 14, 10)
    capa.addWidget(QLabel(titulo, objectName="tenue"))
    principal = QLabel("—", objectName="cifra")
    detalle = QLabel("", objectName="tenue", wordWrap=True)
    capa.addWidget(principal)
    capa.addWidget(detalle)
    botones = QHBoxLayout()
    capa.addLayout(botones)
    return marco, principal, detalle, botones


class PaginaInicio(Pagina):
    titulo = "Inicio"
    subtitulo = "Todo lo importante en una pantalla."

    def __init__(self, app):
        super().__init__()
        self.app = app

        # ---- estado: juego, bot, version
        fila = QHBoxLayout()
        m, self.juego_txt, self.juego_det, bj = _estado("Juego")
        b = QPushButton("Ajustar ventana")
        b.clicked.connect(self._ajustar)
        bj.addWidget(b)
        fila.addWidget(m)
        m, self.bot_txt, self.bot_det, bb = _estado("Bot")
        b = QPushButton("Ver registro")
        b.clicked.connect(lambda: app.navegar("farmear"))
        bb.addWidget(b)
        fila.addWidget(m)
        m, self.ver_txt, self.ver_det, bv = _estado("Version")
        self.b_buscar = QPushButton("Buscar")
        self.b_buscar.setToolTip("Buscar actualizaciones ahora")
        self.b_buscar.clicked.connect(lambda: app.buscar_updates(manual=True))
        self.b_actualizar = QPushButton("⟳  Actualizar", objectName="primario")
        self.b_actualizar.clicked.connect(app.mostrar_bloqueo)
        bv.addWidget(self.b_buscar)
        bv.addWidget(self.b_actualizar)
        fila.addWidget(m)
        self.cuerpo.addLayout(fila)

        # ---- aviso de capturas pendientes
        self.aviso = QFrame(objectName="aviso")
        capa_aviso = QHBoxLayout(self.aviso)
        self.aviso_txt = QLabel(wordWrap=True)
        capa_aviso.addWidget(self.aviso_txt, 1)
        b = QPushButton("Ir a Capturas")
        b.clicked.connect(lambda: app.navegar("capturas"))
        capa_aviso.addWidget(b)
        self.cuerpo.addWidget(self.aviso)

        # ---- arranque rapido + hoy
        fila2 = QHBoxLayout()
        rapido = QGroupBox("Arranque rapido")
        capa_r = QVBoxLayout(rapido)
        self.modo_txt = QLabel(objectName="cifra")
        self.modo_det = QLabel(objectName="tenue", wordWrap=True)
        capa_r.addWidget(self.modo_txt)
        capa_r.addWidget(self.modo_det)
        capa_r.addStretch()
        botones = QHBoxLayout()
        self.b_iniciar = QPushButton("▶  Iniciar ahora", objectName="primario")
        self.b_iniciar.setMinimumHeight(44)
        self.b_iniciar.clicked.connect(lambda: app.farmear.iniciar())
        b_conf = QPushButton("Cambiar modo / opciones")
        b_conf.clicked.connect(lambda: app.navegar("farmear"))
        botones.addWidget(self.b_iniciar, 2)
        botones.addWidget(b_conf, 1)
        capa_r.addLayout(botones)
        fila2.addWidget(rapido, 3)

        hoy = QGroupBox("Hoy")
        rejilla = QGridLayout(hoy)
        self.hoy = {}
        for i, (clave, titulo) in enumerate((("victorias", "Victorias"), ("tasa", "% exito"),
                                             ("por_hora", "Victorias/hora"), ("tiempo", "Tiempo"))):
            marco, cifra = tarjeta(titulo)
            self.hoy[clave] = cifra
            rejilla.addWidget(marco, i // 2, i % 2)
        fila2.addWidget(hoy, 2)
        self.cuerpo.addLayout(fila2)

        consejos = QLabel(
            "Antes de iniciar: juego abierto y visible, ventana ajustada, equipo puesto (Odin, Gawain, Freyja roja, "
            "Thonar azul). Mientras farmea no muevas el raton; para frenar de golpe, llevalo a una esquina.",
            objectName="tenue", wordWrap=True,
        )
        self.cuerpo.addWidget(consejos)
        self.cuerpo.addStretch()

        app.puente.estado.connect(lambda _: self.refrescar())
        app.puente.terminado.connect(self.refrescar)
        QTimer(self, timeout=self.refrescar, interval=3000).start()
        self.refrescar()

    def al_mostrar(self):
        self.refrescar()

    def _ajustar(self):
        if not ventana.ajustar_tamano():
            QMessageBox.warning(self, "Ajustar ventana", ventana.ultimo_error)
        self.refrescar()

    def refrescar(self):
        # juego
        tam = ventana.tamano_actual()
        if tam is None:
            self._pintar(self.juego_txt, "Cerrado", tema.ERROR)
            self.juego_det.setText(f"No encuentro la ventana '{config.obtener('titulo_ventana')}'.")
        elif not ventana.es_admin():
            self._pintar(self.juego_txt, "Sin permisos", tema.AVISO)
            self.juego_det.setText("TrefotFarm no esta como administrador: reabrelo aceptando el aviso de Windows.")
        elif tam == (config.obtener("ancho_ventana"), config.obtener("alto_ventana")):
            self._pintar(self.juego_txt, "Listo", tema.OK)
            self.juego_det.setText(f"Ventana {tam[0]}x{tam[1]}.")
        else:
            self._pintar(self.juego_txt, "Ajustar", tema.AVISO)
            self.juego_det.setText(f"La ventana mide {tam[0]}x{tam[1]}; debe ser 540x960.")

        # bot
        from trefot.control import control

        if self.app.puente.corriendo:
            texto, color = ("En pausa", tema.AVISO) if control.en_pausa else ("Farmeando", tema.OK)
            self._pintar(self.bot_txt, texto, color)
            s = self.app.farmear.ultimas_stats
            self.bot_det.setText(f"{control.estado_actual} · {s.get('victorias', 0)} victorias en esta sesion")
        else:
            self._pintar(self.bot_txt, "Detenido", tema.TENUE)
            self.bot_det.setText("Listo para empezar.")
        self.b_iniciar.setEnabled(not self.app.puente.corriendo)

        # version
        est = self.app.estado_update
        self.ver_txt.setText(f"v{version_local()}")
        if self.app.revisando or est is None:
            self.ver_det.setText("Buscando actualizaciones...")
        elif est.hay_update:
            self.ver_det.setText(f"Actualizacion obligatoria: v{est.version_remota}")
        elif est.error:
            self.ver_det.setText(est.error)
        else:
            self.ver_det.setText(f"Al dia · revisado a las {time.strftime('%H:%M', time.localtime(est.revisado))}")
        self.b_buscar.setEnabled(not self.app.revisando)
        self.b_actualizar.setEnabled(bool(est and est.hay_update))

        # capturas y modo
        modo = MODOS.get(config.obtener("ultimo_modo")) or next(iter(MODOS.values()))
        self.modo_txt.setText(modo.nombre)
        self.modo_det.setText(modo.descripcion)
        faltan = modo.equipo.faltantes() if getattr(modo, "equipo", None) else []
        self.aviso.setVisible(bool(faltan))
        if faltan:
            self.aviso_txt.setText(
                f"<b>Faltan {len(faltan)} capturas obligatorias</b> para '{modo.nombre}': "
                + ", ".join(d.descripcion for d in faltan)
            )

        # hoy
        t = historial.totales(historial.hoy(historial.leer()))
        self.hoy["victorias"].setText(str(t["victorias"]))
        self.hoy["tasa"].setText(f"{t['tasa']:.0f}%")
        self.hoy["por_hora"].setText(f"{t['por_hora']:.1f}")
        self.hoy["tiempo"].setText(formatear_tiempo(t["segundos"]))

    @staticmethod
    def _pintar(etiqueta: QLabel, texto: str, color: str):
        etiqueta.setText(texto)
        etiqueta.setStyleSheet(f"color: {color}")

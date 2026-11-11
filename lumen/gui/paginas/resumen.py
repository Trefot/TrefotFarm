"""Navegacion por tareas y resumen de datos reales."""

from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QProgressBar,
)
from lumen import config, historial, metas
from lumen.gui import tema
from lumen.gui.actualizaciones import PanelActualizaciones
from lumen.gui.aventura import PanelAventura, escena_taberna
from lumen.rutas import ASSETS
from lumen.gui.comun import Pagina, tarjeta, formatear_tiempo
from lumen.gui.catalogo_visual import CatalogoVisual
from lumen.modos.catalogo import CATALOGO, contenido_de
from lumen.gui.paginas.equipos import tarjetas_equipos, clave_de_equipos


def accion(texto, callback, primario=False):
    b = QPushButton(texto, objectName="primario" if primario else "accion_card")
    b.clicked.connect(callback)
    return b


def panel(titulo, descripcion):
    marco = QFrame(objectName="contenido_card")
    capa = QVBoxLayout(marco)
    capa.setContentsMargins(24, 24, 24, 24)
    capa.setSpacing(12)
    capa.addWidget(QLabel(titulo, objectName="titulo_card", wordWrap=True))
    capa.addWidget(QLabel(descripcion, objectName="tenue", wordWrap=True))
    return marco, capa


class PaginaResumen(Pagina):
    titulo = "Tu centro de farmeo"
    subtitulo = (
        "Prepara tu próxima sesión y encuentra todo lo que necesitas para jugar."
    )
    desplazable = True

    def __init__(self, app):
        if tema.SKIN.id == "taberna_viva":
            self.titulo = "Bienvenido a la taberna"
            self.subtitulo = "Un descanso entre batallas. Todo listo para tu próxima aventura."
        super().__init__()
        self.app = app
        self.actualizaciones = PanelActualizaciones(app)
        self.cuerpo.addWidget(self.actualizaciones)
        if tema.SKIN.id == "taberna_viva":
            self._construir_taberna(app)
            return
        hero, capa = panel(
            "¿Qué quieres conseguir hoy?",
            "Elige un contenido, revisa los requisitos y deja preparada tu sesión de 7DS.",
        )
        hero.setObjectName("hero")
        capa.addWidget(QLabel("ELEGIR → PREPARAR → INICIAR", objectName="eyebrow"))
        botones = QHBoxLayout()
        botones.addWidget(
            accion("Explorar contenidos  →", lambda: app.navegar("contenidos"), True)
        )
        botones.addWidget(
            accion("Ver sesión en directo", lambda: app.navegar("farmear"))
        )
        botones.addStretch()
        capa.addLayout(botones)
        self.cuerpo.addWidget(hero)
        self.cuerpo.addWidget(QLabel("Tu actividad de hoy", objectName="titulo_card"))
        fila = QHBoxLayout()
        self.cifras = {}
        for clave, titulo in (
            ("sesiones", "Sesiones"),
            ("victorias", "Victorias"),
            ("segundos", "Tiempo de juego"),
        ):
            w, cifra = tarjeta(titulo)
            self.cifras[clave] = cifra
            fila.addWidget(w)
        self.cuerpo.addLayout(fila)
        fila = QHBoxLayout()
        for titulo, descripcion, destino in (
            (
                "Plan del día",
                "Ordena las tareas y prepara una secuencia de farmeo.",
                "plan",
            ),
            (
                "Mis equipos",
                "Consulta los equipos registrados para cada contenido.",
                "mis_equipos",
            ),
            (
                "Objetivos de materiales",
                "Decide qué reunir y consulta cuánto te falta.",
                "objetivos",
            ),
        ):
            w, c = panel(titulo, descripcion)
            c.addStretch()
            c.addWidget(
                accion("Abrir apartado  →", lambda _, d=destino: app.navegar(d))
            )
            fila.addWidget(w, 1)
        self.cuerpo.addLayout(fila)
        w, c = panel(
            "Continúa preparando tu sesión",
            "La selección más reciente queda aquí para que puedas retomarla.",
        )
        self.seleccion = QLabel(objectName="titulo_card", wordWrap=True)
        c.addWidget(self.seleccion)
        c.addWidget(accion("Revisar preparación  →", lambda: app.navegar("preparar")))
        self.cuerpo.addWidget(w)
        self.cuerpo.addStretch()

    def _construir_taberna(self, app):
        hero = escena_taberna()
        capa = QVBoxLayout(hero)
        capa.setContentsMargins(30, 26, 30, 24)
        capa.setSpacing(12)
        capa.addWidget(
            QLabel(
                "LUZ ENCENDIDA · AVENTURAS POR DELANTE", objectName="rotulo_aventura"
            )
        )
        titulo = QLabel(
            "Tu próxima aventura\nempieza aquí.",
            objectName="titulo_hero",
            wordWrap=True,
        )
        capa.addWidget(titulo)
        descripcion = QLabel(
            "Elige tu destino, reúne a tu equipo\ny prepárate para volver con el botín.",
            objectName="detalle_aventura",
            wordWrap=True,
        )
        descripcion.setMaximumWidth(470)
        capa.addWidget(descripcion)
        capa.addStretch()
        fila = QHBoxLayout()
        fila.addWidget(
            accion("Elegir aventura  →", lambda: app.navegar("contenidos"), True)
        )
        fila.addWidget(accion("Ir a mi sesión", lambda: app.navegar("farmear")))
        fila.addStretch()
        capa.addLayout(fila)
        self.seleccion = QLabel(objectName="detalle_aventura", wordWrap=True)
        capa.addWidget(self.seleccion)
        self.cuerpo.addWidget(hero)
        cabecera = QHBoxLayout()
        cabecera.addWidget(QLabel("El tablón de la taberna", objectName="titulo_card"))
        cabecera.addStretch()
        cabecera.addWidget(
            QLabel("Tus preparativos, siempre a mano", objectName="tenue")
        )
        self.cuerpo.addLayout(cabecera)
        fila = QHBoxLayout()
        for titulo, descripcion, destino, imagen in (
            (
                "Plan del día",
                "Una ruta. Varias misiones.",
                "plan",
                ASSETS / "modos" / "perros_piso4.png",
            ),
            (
                "Mis equipos",
                "Compañeros para cada batalla.",
                "mis_equipos",
                ASSETS / "personajes" / "adventurer_ban_verde" / "artwork.jpg",
            ),
            (
                "Mis objetivos",
                "Cada material te acerca a tu meta.",
                "objetivos",
                ASSETS / "modos" / "oro.png",
            ),
        ):
            w = PanelAventura(imagen)
            c = QVBoxLayout(w)
            c.setContentsMargins(18, 18, 18, 18)
            c.addWidget(QLabel(titulo, objectName="titulo_card", wordWrap=True))
            detalle = QLabel(descripcion, objectName="detalle_aventura", wordWrap=True)
            detalle.setMaximumWidth(230)
            c.addWidget(detalle)
            c.addStretch()
            c.addWidget(accion("Abrir  →", lambda _, d=destino: app.navegar(d)))
            fila.addWidget(w, 1)
        self.cuerpo.addLayout(fila)
        self.cuerpo.addWidget(QLabel("El balance de hoy", objectName="titulo_card"))
        fila = QHBoxLayout()
        self.cifras = {}
        for clave, titulo in (
            ("sesiones", "Expediciones"),
            ("victorias", "Victorias"),
            ("segundos", "Tiempo de aventura"),
        ):
            w, cifra = tarjeta(titulo)
            self.cifras[clave] = cifra
            fila.addWidget(w)
        self.cuerpo.addLayout(fila)
        self.cuerpo.addStretch()

    def refrescar(self):
        self.actualizaciones.refrescar()
        t = historial.totales(historial.hoy(historial.leer()))
        for clave, cifra in self.cifras.items():
            cifra.setText(
                formatear_tiempo(t[clave]) if clave == "segundos" else str(t[clave])
            )
        contenido = contenido_de(
            config.obtener("ultimo_destino") or config.obtener("ultimo_modo")
        )
        self.seleccion.setText(
            ("Último destino · " if tema.SKIN.id == "taberna_viva" else "")
            + contenido.nombre
            if contenido
            else "Aún no has elegido un contenido"
        )

    def al_mostrar(self):
        self.refrescar()


class PaginaContenidos(Pagina):
    titulo = "Explorar contenidos"
    subtitulo = (
        "Elige un destino, descubre sus opciones y prepara tu próxima aventura."
    )
    desplazable = True

    def __init__(self, app):
        super().__init__()
        self.catalogo = CatalogoVisual()
        self.catalogo.elegido.connect(lambda destino: self._elegir(app, destino))
        self.cuerpo.addWidget(self.catalogo)
        self.cuerpo.addStretch()

    def _elegir(self, app, destino):
        app.paginas["preparar"].ir_a_destino(destino)
        app.navegar("preparar")


class PaginaPlan(Pagina):
    titulo = "Plan del día"
    subtitulo = (
        "Organiza las tareas en orden y controla la secuencia desde un solo lugar."
    )
    desplazable = True

    def __init__(self, app):
        super().__init__()
        self.cuerpo.addWidget(app.farmear.panel_plan)
        self.cuerpo.addStretch()


class PaginaMisEquipos(Pagina):
    titulo = "Mis equipos"
    subtitulo = "Consulta tus opciones por contenido. La edición de la base está reservada a Administración."
    desplazable = True

    def __init__(self, app):
        super().__init__()
        self.selector = QComboBox()
        for contenido in CATALOGO:
            for d in contenido.destinos:
                self.selector.addItem(contenido.nombre + " · " + d.nombre, d.id)
        self.cuerpo.addWidget(self.selector)
        self.lista = QVBoxLayout()
        self.cuerpo.addLayout(self.lista)
        self.cuerpo.addStretch()
        self.selector.currentIndexChanged.connect(self.al_mostrar)

    def al_mostrar(self):
        while self.lista.count():
            item = self.lista.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        tarjetas = tarjetas_equipos(clave_de_equipos(self.selector.currentData()))
        for w in tarjetas:
            self.lista.addWidget(w)
        if not tarjetas:
            self.lista.addWidget(
                QLabel(
                    "Todavía no hay equipos registrados para este contenido.",
                    wordWrap=True,
                )
            )


class PaginaObjetivos(Pagina):
    titulo = "Objetivos de materiales"
    subtitulo = (
        "Sigue tus metas y ajusta las cantidades desde la preparación del contenido."
    )
    desplazable = True

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.acciones.addWidget(
            accion("Elegir material  →", lambda: app.navegar("contenidos"))
        )

    def al_mostrar(self):
        while self.cuerpo.count():
            item = self.cuerpo.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        objetivos = metas.cargar()
        for meta in objetivos:
            w, c = panel(
                meta.nombre, f"{meta.actual} de {meta.quiero} · Faltan {meta.faltan}"
            )
            progreso = QProgressBar()
            progreso.setRange(0, max(1, meta.quiero))
            progreso.setValue(min(meta.actual, meta.quiero))
            c.addWidget(progreso)
            c.addWidget(
                accion(
                    "Ajustar objetivo",
                    lambda _, o=meta.objeto: self._abrir_meta(o),
                )
            )
            self.cuerpo.addWidget(w)
        if not objetivos:
            w, c = panel(
                "Tu próximo objetivo empieza con un material",
                "Entra en un contenido y toca uno de sus materiales para indicar cuánto tienes y cuánto quieres conseguir.",
            )
            c.addWidget(
                accion(
                    "Explorar contenidos  →",
                    lambda: self.app.navegar("contenidos"),
                    True,
                )
            )
            self.cuerpo.addWidget(w)
        self.cuerpo.addStretch()

    def _abrir_meta(self, objeto):
        destino = metas.mejor_destino(objeto)
        self.app.paginas["preparar"].abrir_meta(objeto, destino[0] if destino else None)

"""Asistente de primera vez: explica el bot paso a paso a alguien que nunca lo uso.

Sale solo la primera vez que se abre LumenFarm (config "asistente_visto") y se puede volver a abrir
desde Ajustes.
"""

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from lumen import accesos, config, ventana
from lumen import personajes as P
from lumen.gui import iconos, tema
from lumen.gui.paginas.personajes import TarjetaPersonaje
from lumen.modos import MODOS
from lumen.rutas import IMAGENES

PASOS = ["Bienvenida", "El juego", "Personajes", "Equipo", "Seguridad", "¡Listo!"]


def _texto(html: str, nombre: str | None = None) -> QLabel:
    etiqueta = QLabel(html, wordWrap=True)
    etiqueta.setTextFormat(Qt.RichText)
    if nombre:
        etiqueta.setObjectName(nombre)
    return etiqueta


def _punto(icono: str, titulo: str, detalle: str) -> QFrame:
    """Fila con un icono redondo, un titulo y una explicacion."""
    marco = QFrame(objectName="paso")
    fila = QHBoxLayout(marco)
    fila.setContentsMargins(12, 10, 12, 10)
    fila.setSpacing(12)
    dibujo = QLabel(objectName="icono_tarjeta", alignment=Qt.AlignCenter)
    dibujo.setPixmap(iconos.pixmap(icono, 24, tema.ACENTO))
    dibujo.setFixedSize(44, 44)
    fila.addWidget(dibujo, 0, Qt.AlignTop)
    textos = QVBoxLayout()
    textos.setSpacing(2)
    textos.addWidget(QLabel(f"<b>{titulo}</b>"))
    textos.addWidget(_texto(detalle, "tenue"))
    fila.addLayout(textos, 1)
    return marco


def _equipos() -> list:
    """Los equipos de los modos que existen, sin repetir."""
    vistos, lista = set(), []
    for modo in MODOS.values():
        equipo = getattr(modo, "equipo", None)
        if equipo is not None and equipo.id not in vistos:
            vistos.add(equipo.id)
            lista.append((modo, equipo))
    return lista


class Asistente(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bienvenido a LumenFarm")
        self.setModal(True)
        self.resize(880, 640)
        self.setMinimumSize(820, 600)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(24, 18, 24, 18)
        raiz.setSpacing(14)

        # ---- indicador de pasos
        self.marcas: list[QLabel] = []
        fila_pasos = QHBoxLayout()
        fila_pasos.setSpacing(6)
        for i, nombre in enumerate(PASOS):
            marca = QLabel(f"{i + 1}  {nombre}", objectName="fase", alignment=Qt.AlignCenter)
            self.marcas.append(marca)
            fila_pasos.addWidget(marca, 1)
        raiz.addLayout(fila_pasos)
        separador = QFrame(objectName="separador_oro")
        raiz.addWidget(separador)

        # ---- paginas
        self.pila = QStackedWidget()
        for crear in (self._bienvenida, self._juego, self._personajes, self._equipo, self._seguridad, self._listo):
            self.pila.addWidget(crear())
        raiz.addWidget(self.pila, 1)

        # ---- botones
        botones = QHBoxLayout()
        self.b_saltar = QPushButton("Saltar el asistente", objectName="chico")
        self.b_saltar.clicked.connect(self.accept)
        botones.addWidget(self.b_saltar)
        botones.addStretch()
        self.b_atras = QPushButton(" Atrás")
        self.b_atras.setIcon(iconos.icono("mdi6.arrow-left", tema.TEXTO))
        self.b_atras.clicked.connect(lambda: self._ir(self.pila.currentIndex() - 1))
        botones.addWidget(self.b_atras)
        self.b_siguiente = QPushButton("Siguiente ", objectName="primario")
        self.b_siguiente.setLayoutDirection(Qt.RightToLeft)
        self.b_siguiente.setIcon(iconos.icono("flecha", tema.SOBRE_ACENTO))
        self.b_siguiente.setIconSize(QSize(18, 18))
        self.b_siguiente.setMinimumWidth(150)
        self.b_siguiente.setMinimumHeight(40)
        self.b_siguiente.clicked.connect(self._siguiente)
        botones.addWidget(self.b_siguiente)
        raiz.addLayout(botones)
        self._ir(0)

    # ------------------------------------------------------------------ navegacion
    def _ir(self, indice: int):
        indice = max(0, min(indice, self.pila.count() - 1))
        self.pila.setCurrentIndex(indice)
        for i, marca in enumerate(self.marcas):
            marca.setProperty("estado", "actual" if i == indice else "hecha" if i < indice else "")
            marca.style().unpolish(marca)
            marca.style().polish(marca)
        ultimo = indice == self.pila.count() - 1
        self.b_atras.setEnabled(indice > 0)
        self.b_saltar.setVisible(not ultimo)
        self.b_siguiente.setText("Empezar a usarlo " if ultimo else "Siguiente ")
        if indice == 1:
            self._comprobar_juego()
        if indice == 3:
            self._pintar_equipo()
        self._validar()

    def _siguiente(self):
        if self.pila.currentIndex() == self.pila.count() - 1:
            self.accept()
        else:
            self._ir(self.pila.currentIndex() + 1)

    def _validar(self):
        # En la bienvenida hay que aceptar el aviso antes de seguir.
        self.b_siguiente.setEnabled(self.pila.currentIndex() != 0 or self.acepto.isChecked())

    def done(self, resultado):
        config.guardar({"asistente_visto": True})
        super().done(resultado)

    # ------------------------------------------------------------------ paginas
    def _pagina(self, titulo: str, subtitulo: str) -> tuple[QWidget, QVBoxLayout]:
        w = QWidget()
        capa = QVBoxLayout(w)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(10)
        capa.addWidget(QLabel(titulo, objectName="titulo_pagina"))
        capa.addWidget(_texto(subtitulo, "tenue"))
        capa.addSpacing(4)
        return w, capa

    def _bienvenida(self) -> QWidget:
        w, capa = self._pagina("¡Hola! Soy Lumen Farm",
                               "Juego por ti las peleas repetitivas de The Seven Deadly Sins: Grand Cross "
                               "mientras tú haces otra cosa. En un par de minutos te explico cómo usarme.")
        capa.addWidget(_punto("farmear", "Farmeo solo",
                              "Entro a la pelea, juego las cartas con un guion probado, cobro el botín y repito."))
        capa.addWidget(_punto("recompensas", "Cuento lo que ganas",
                              "Cada victoria guarda su botín: oro y objetos, sumados en la página Botín."))
        capa.addWidget(_punto("movil", "Te aviso al móvil",
                              "Si quieres, te mando un aviso si algo se atasca o si el juego pide reiniciarse."))
        aviso = QFrame(objectName="aviso")
        capa_aviso = QVBoxLayout(aviso)
        capa_aviso.addWidget(_texto(
            "<b>Importante:</b> usar bots va contra las reglas de Netmarble y puede costar un baneo de la cuenta. "
            "Úsalo bajo tu propia responsabilidad."))
        self.acepto = QCheckBox("Lo entiendo y quiero seguir")
        self.acepto.toggled.connect(self._validar)
        capa_aviso.addWidget(self.acepto)
        capa.addWidget(aviso)
        capa.addStretch()
        return w

    def _juego(self) -> QWidget:
        w, capa = self._pagina("Prepara el juego",
                               "Abre el juego y llega a la Tavern. Yo compruebo lo demás aquí abajo.")
        rejilla = QGridLayout()
        rejilla.setSpacing(10)
        self.chequeos: dict[str, tuple[QLabel, QLabel]] = {}
        for i, (clave, titulo) in enumerate((("juego", "Juego abierto"), ("admin", "Permiso de administrador"),
                                             ("tamano", "Tamaño de la ventana"))):
            marco = QFrame(objectName="paso")
            fila = QHBoxLayout(marco)
            fila.setContentsMargins(12, 10, 12, 10)
            icono = QLabel()
            fila.addWidget(icono)
            textos = QVBoxLayout()
            textos.setSpacing(2)
            textos.addWidget(QLabel(f"<b>{titulo}</b>"))
            detalle = _texto("", "tenue")
            textos.addWidget(detalle)
            fila.addLayout(textos, 1)
            self.chequeos[clave] = (icono, detalle)
            rejilla.addWidget(marco, i, 0)
        capa.addLayout(rejilla)
        b = QPushButton(" Comprobar otra vez", objectName="chico")
        b.setIcon(iconos.icono("actualizar", tema.TEXTO))
        b.clicked.connect(self._comprobar_juego)
        fila_b = QHBoxLayout()
        fila_b.addWidget(b)
        fila_b.addStretch()
        capa.addLayout(fila_b)
        capa.addWidget(_punto("juego", "Qué versión del juego",
                              "La de PC del servidor Global, con el juego en inglés. Japón y otros idiomas "
                              "llegarán más adelante."))
        capa.addWidget(_punto("ventana", "No te preocupes por el tamaño",
                              "Al empezar a farmear pongo la ventana del juego en el tamaño que necesito. "
                              "No la tapes con otras ventanas mientras juego."))
        capa.addStretch()
        return w

    def _comprobar_juego(self):
        tam = ventana.tamano_actual()
        admin = ventana.es_admin()
        resultados = {
            "juego": (tam is not None, "Lo encuentro." if tam else "No lo encuentro. Ábrelo y pulsa Comprobar otra vez."),
            "admin": (admin, "Lo tengo." if admin else "Cierra LumenFarm, ábrelo otra vez y acepta el aviso de Windows."),
            "tamano": (bool(tam and ventana.tamano_correcto(tam)),
                       "Correcto." if tam and ventana.tamano_correcto(tam)
                       else "Lo ajusto yo al empezar." if tam else "Primero abre el juego."),
        }
        for clave, (ok, texto) in resultados.items():
            icono, detalle = self.chequeos[clave]
            icono.setPixmap(iconos.pixmap("ok" if ok else "falta", 26, tema.OK if ok else tema.AVISO))
            detalle.setText(texto)

    def _personajes(self) -> QWidget:
        w, capa = self._pagina("¿Qué personajes tienes?",
                               "Haz clic en los que tengas en el juego: se ponen a color. Así sé qué puedes "
                               "farmear. El resto de personajes los marcas en la página Personajes.")
        self.zona_pj = QGridLayout()
        self.zona_pj.setSpacing(12)
        self.zona_pj.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        capa.addLayout(self.zona_pj)
        self.lbl_pj = _texto("", "tenue")
        capa.addWidget(self.lbl_pj)
        capa.addStretch()
        self._pintar_personajes()
        return w

    def _pintar_personajes(self):
        while self.zona_pj.count():
            item = self.zona_pj.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        biblioteca = P.cargar()
        fila = 0
        for modo, equipo in _equipos():
            self.zona_pj.addWidget(QLabel(f"Para {modo.titulo_juego or modo.nombre}", objectName="titulo_seccion"),
                                   fila, 0, 1, 6)
            fila += 1
            for col, pid in enumerate(equipo.orden):
                pj = biblioteca.get(pid)
                if pj is None:
                    continue
                tarjeta = TarjetaPersonaje(pj, [])
                tarjeta.cambiado.connect(self._marcar)
                self.zona_pj.addWidget(tarjeta, fila, col)
            fila += 1
        tengo = sum(1 for p in biblioteca.values() if p.tengo)
        self.lbl_pj.setText(f"Tienes marcados {tengo} personajes.")

    def _marcar(self, pid: str, tengo: bool):
        P.marcar_tengo(pid, tengo)
        self._pintar_personajes()

    def _equipo(self) -> QWidget:
        w, capa = self._pagina("Arma el equipo en el juego",
                               "Antes de farmear, pon este equipo en el juego <b>en este orden, de izquierda a "
                               "derecha</b>. Yo lo compruebo al empezar y te aviso si algo no cuadra.")
        self.zona_equipo = QVBoxLayout()
        self.zona_equipo.setSpacing(10)
        capa.addLayout(self.zona_equipo)
        capa.addStretch()
        return w

    def _pintar_equipo(self):
        while self.zona_equipo.count():
            item = self.zona_equipo.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        biblioteca = P.cargar()
        for modo, equipo in _equipos():
            caja = QFrame(objectName="seccion")
            capa = QVBoxLayout(caja)
            capa.setContentsMargins(16, 12, 16, 14)
            cabecera = QHBoxLayout()
            emblema = QLabel()
            pix = iconos.redondo(IMAGENES / modo.imagen, 46, tema.ACENTO) if modo.imagen else None
            if pix:
                emblema.setPixmap(pix)
            cabecera.addWidget(emblema)
            cabecera.addWidget(QLabel(modo.titulo_juego or modo.nombre, objectName="titulo_tarjeta"), 1)
            capa.addLayout(cabecera)
            fila = QHBoxLayout()
            fila.setSpacing(10)
            for n, puesto in enumerate(equipo.puestos, start=1):
                pj = biblioteca.get(puesto.recomendado)
                hueco = QFrame(objectName="paso")
                capa_h = QVBoxLayout(hueco)
                capa_h.setContentsMargins(10, 10, 10, 10)
                capa_h.setSpacing(4)
                capa_h.addWidget(QLabel(f"Puesto {n}", objectName="lema", alignment=Qt.AlignCenter))
                foto = QLabel(alignment=Qt.AlignCenter)
                retrato = iconos.redondo(pj.ruta_cara(), 72, tema.ACENTO if pj.tengo else tema.BORDE) if pj else None
                if retrato:
                    foto.setPixmap(retrato)
                capa_h.addWidget(foto)
                nombre = pj.nombre if pj else puesto.recomendado
                color = P.NOMBRE_COLOR.get(pj.color, "") if pj else ""
                capa_h.addWidget(QLabel(f"<b>{nombre}</b>" + (f" · {color}" if color else ""), alignment=Qt.AlignCenter))
                capa_h.addWidget(_texto(puesto.funcion, "tenue"))
                if pj and not pj.tengo:
                    capa_h.addWidget(QLabel(f"<span style='color:{tema.AVISO}'>No lo tienes marcado</span>",
                                            alignment=Qt.AlignCenter))
                fila.addWidget(hueco, 1)
            capa.addLayout(fila)
            self.zona_equipo.addWidget(caja)
        self.zona_equipo.addWidget(_punto(
            "equipos", "¿No tienes a alguno?",
            "En la página Equipos verás otras opciones para cada Demonic Beast. Más adelante podré jugar "
            "con cualquier equipo."))

    def _seguridad(self) -> QWidget:
        w, capa = self._pagina("Mientras farmeo",
                               "Yo muevo el ratón de verdad, así que mientras juego el ratón es mío.")
        pausa = str(config.obtener("tecla_pausa")).upper()
        detener = str(config.obtener("tecla_detener")).upper()
        capa.addWidget(_punto("pausa", f"{pausa} para pausar",
                              f"Si necesitas el ratón un momento, pulsa {pausa}. Vuelve a pulsarla para seguir."))
        capa.addWidget(_punto("detener", f"{detener} para detener",
                              "Paro del todo. Funciona aunque el juego esté al frente."))
        capa.addWidget(_punto("mdi6.cursor-default-click-outline", "Freno de emergencia",
                              "Lleva el ratón de golpe a una esquina de la pantalla y me detengo al instante."))
        capa.addWidget(_punto("ventana", "No tapes el juego",
                              "Veo el juego mirando la pantalla: si otra ventana lo tapa, me pierdo."))
        capa.addWidget(_punto("actualizar", "Me actualizo solo",
                              "Cuando hay una versión nueva te pido actualizar antes de seguir: así siempre "
                              "juegas con el guion más reciente."))
        capa.addStretch()
        return w

    def _listo(self) -> QWidget:
        w, capa = self._pagina("¡Todo listo!",
                               "Ya sabes lo básico. Para farmear, ve a <b>Inicio</b>:")
        capa.addWidget(_punto("ok", "1. Mira los 4 iconos de arriba", "En verde = listo. Toca uno para arreglarlo."))
        capa.addWidget(_punto("farmear", "2. Gira la rueda", "Elige qué farmear y su piso."))
        capa.addWidget(_punto("trofeo", "3. Elige cuántas victorias", "Un número fijo, o sin límite."))
        capa.addWidget(_punto("jugar", "4. Pulsa Empezar", "Y déjame el ratón. En Farmear ves qué estoy haciendo."))
        self.crear_acceso = QCheckBox("Crear un acceso directo en el escritorio y en el menú Inicio")
        self.crear_acceso.setChecked(True)
        self.crear_acceso.setVisible(not accesos.existen())
        capa.addWidget(self.crear_acceso)
        capa.addWidget(_texto("¿Dudas? En <b>Ayuda</b> tienes una guía con capturas del juego, soluciones a los problemas "
                              "más comunes y un glosario. Desde ahí también puedes volver a abrir este asistente.", "tenue"))
        capa.addStretch()
        return w

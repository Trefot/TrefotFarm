"""Estilo visual de la interfaz: skins con aire del juego (azul noche y dorado) y skins de temporada.

La skin se elige al arrancar: la de la fecha (Halloween, Navidad...) si config "skin" es "auto",
o la que el usuario fijo en Ajustes. Cambiarla pide reiniciar, porque las paginas leen estos
colores al construirse.
"""

import datetime
from dataclasses import dataclass, field

from lumen import config
from lumen.rutas import ASSETS

CARPETA_FUENTES = ASSETS / "fuentes"
FUENTE_TITULOS = "Cinzel"
FUENTE_MARCA = "Cinzel Decorative"


@dataclass(frozen=True)
class Skin:
    id: str
    nombre: str
    fondo: str
    lateral: str
    panel: str
    panel_alto: str  # parte de arriba del degradado de los paneles
    borde: str
    borde_oro: str  # marco dorado de lo seleccionado / destacado
    texto: str
    tenue: str
    acento: str
    acento_claro: str
    sobre_acento: str  # texto encima del acento
    seleccion: str  # fondo de una tarjeta elegida
    hundido: str  # cajas de texto, listas
    profundo: str  # fondo de imagenes
    icono: str = ""  # adorno de temporada (Material Design Icons)
    saludo: str = ""
    fechas: tuple = field(default=())  # ((mes, dia_desde), (mes, dia_hasta)), puede cruzar de año


SKINS = {
    "taberna": Skin(
        "taberna", "Boar Hat (normal)",
        fondo="#11141d", lateral="#0b0d14", panel="#191e2b", panel_alto="#212839", borde="#2b3245",
        borde_oro="#8a6a2c", texto="#ece6d6", tenue="#8f93a6", acento="#e2b04a", acento_claro="#f3cc72",
        sobre_acento="#1d1405", seleccion="#2a2416", hundido="#0d1018", profundo="#080a10",
    ),
    "halloween": Skin(
        "halloween", "Halloween",
        fondo="#130e18", lateral="#0c0810", panel="#1e1626", panel_alto="#2a1d35", borde="#3a2a48",
        borde_oro="#a2541c", texto="#efe3f2", tenue="#9a8aa6", acento="#ff8c26", acento_claro="#ffab5c",
        sobre_acento="#1f0d02", seleccion="#2e1c17", hundido="#0e0a13", profundo="#08060b",
        icono="mdi6.halloween", saludo="¡Feliz Halloween!", fechas=((10, 15), (11, 2)),
    ),
    "navidad": Skin(
        "navidad", "Navidad",
        fondo="#0d1612", lateral="#08100c", panel="#14211b", panel_alto="#1b2d25", borde="#27402f",
        borde_oro="#a08236", texto="#eef3ea", tenue="#8ea597", acento="#e4b94e", acento_claro="#f5d27a",
        sobre_acento="#1d1405", seleccion="#2c2a17", hundido="#09110d", profundo="#060b08",
        icono="mdi6.pine-tree", saludo="¡Feliz Navidad!", fechas=((12, 1), (12, 29)),
    ),
    "ano_nuevo": Skin(
        "ano_nuevo", "Año Nuevo",
        fondo="#0f1020", lateral="#090a16", panel="#181a31", panel_alto="#22254a", borde="#30345a",
        borde_oro="#9b8a3c", texto="#eef0fb", tenue="#9195b8", acento="#f0cf55", acento_claro="#fbe28c",
        sobre_acento="#1d1705", seleccion="#2b2a1c", hundido="#0b0c19", profundo="#07070f",
        icono="mdi6.party-popper", saludo="¡Feliz Año Nuevo!", fechas=((12, 30), (1, 6)),
    ),
    "san_valentin": Skin(
        "san_valentin", "San Valentín",
        fondo="#180f15", lateral="#10090e", panel="#251620", panel_alto="#331d2b", borde="#482a3c",
        borde_oro="#a3466c", texto="#f7e8ef", tenue="#a9899a", acento="#ff6f9c", acento_claro="#ff9bbb",
        sobre_acento="#220812", seleccion="#33192a", hundido="#120a10", profundo="#0b060a",
        icono="mdi6.heart", saludo="¡Feliz San Valentín!", fechas=((2, 7), (2, 15)),
    ),
    "aniversario": Skin(
        "aniversario", "Aniversario de Grand Cross",
        fondo="#10131f", lateral="#0a0c15", panel="#1a1f33", panel_alto="#262c49", borde="#323a5c",
        borde_oro="#b08a35", texto="#f2ecdc", tenue="#9599b6", acento="#ffc94a", acento_claro="#ffdc85",
        sobre_acento="#1f1503", seleccion="#2f2a19", hundido="#0c0e18", profundo="#070810",
        icono="mdi6.cake-variant", saludo="¡Feliz aniversario de Grand Cross!", fechas=((3, 1), (3, 10)),
    ),
}
NORMAL = "taberna"


def _en_fechas(skin: Skin, hoy: datetime.date) -> bool:
    if not skin.fechas:
        return False
    desde, hasta = skin.fechas
    actual = (hoy.month, hoy.day)
    if desde <= hasta:
        return desde <= actual <= hasta
    return actual >= desde or actual <= hasta  # cruza el cambio de año


def skin_de_fecha(hoy: datetime.date | None = None) -> Skin:
    hoy = hoy or datetime.date.today()
    for skin in SKINS.values():
        if _en_fechas(skin, hoy):
            return skin
    return SKINS[NORMAL]


def elegir_skin() -> Skin:
    elegida = str(config.obtener("skin", "auto"))
    return SKINS.get(elegida) or skin_de_fecha()


def cargar_fuentes() -> None:
    """Registra las fuentes de assets/fuentes. Hay que llamarla despues de crear la QApplication."""
    from PyQt5.QtGui import QFontDatabase

    for archivo in sorted(CARPETA_FUENTES.glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(archivo))


SKIN = elegir_skin()

FONDO = SKIN.fondo
LATERAL = SKIN.lateral
PANEL = SKIN.panel
BORDE = SKIN.borde
TEXTO = SKIN.texto
TENUE = SKIN.tenue
ACENTO = SKIN.acento
SOBRE_ACENTO = SKIN.sobre_acento
OK = "#4cc38a"
AVISO = "#e6b84c"
ERROR = "#ef6461"
DEBUG = "#6b7186"

COLOR_NIVEL = {"info": TEXTO, "ok": OK, "aviso": AVISO, "error": ERROR, "debug": DEBUG}

_s = SKIN
_PANEL = f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {_s.panel_alto}, stop:1 {_s.panel})"
_ORO = f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {_s.acento_claro}, stop:0.5 {_s.acento}, stop:1 {_s.borde_oro})"
_ORO_HOVER = f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fff3cf, stop:0.5 {_s.acento_claro}, stop:1 {_s.acento})"
_SEL = f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {_s.seleccion}, stop:1 {_s.panel})"
_TITULOS = f"'{FUENTE_TITULOS}', 'Segoe UI'"

HOJA = f"""
QWidget {{ background: {_s.fondo}; color: {_s.texto}; font-family: 'Segoe UI'; font-size: 10pt; }}
QLabel, QCheckBox {{ background: transparent; }}
QToolTip {{ background: {_s.panel_alto}; color: {_s.texto}; border: 1px solid {_s.borde_oro}; padding: 4px; }}

/* ---- menu lateral */
QFrame#lateral {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_s.lateral}, stop:1 {_s.fondo});
                  border-right: 1px solid {_s.borde_oro}; }}
QLabel#marca {{ font-family: {_TITULOS}; font-size: 10pt; font-weight: 700; color: {_s.acento}; letter-spacing: 3px; }}
QLabel#lema {{ font-family: {_TITULOS}; color: {_s.tenue}; font-size: 8.5pt; letter-spacing: 2px; padding-left: 5px; }}
QFrame#saludo {{ background: {_SEL}; border: 1px solid {_s.borde_oro}; border-radius: 8px; }}
QFrame#saludo QLabel {{ color: {_s.acento_claro}; font-family: {_TITULOS}; font-weight: 700; font-size: 9pt; }}
QFrame#separador_oro {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 transparent, stop:0.5 {_s.borde_oro},
                        stop:1 transparent); min-height: 1px; max-height: 1px; border: none; }}
QToolButton#menu {{ padding: 7px 2px 5px 2px; border: 1px solid transparent; border-radius: 12px; min-width: 76px;
                    color: {_s.tenue}; font-size: 8.5pt; background: transparent; }}
QToolButton#menu:hover {{ background: {_s.panel}; color: {_s.texto}; }}
QToolButton#menu:checked {{ background: {_SEL}; color: {_s.acento}; font-weight: 700; border: 1px solid {_s.borde_oro}; }}
QToolButton#menu:disabled {{ color: {_s.borde}; }}
QLabel#insignia {{ background: {ERROR}; color: white; border-radius: 8px; padding: 0 5px; font-size: 7.5pt; font-weight: 700; }}

/* ---- paginas */
QLabel#titulo_pagina {{ font-family: {_TITULOS}; font-size: 19pt; font-weight: 700; color: {_s.acento}; }}
QLabel#cifra {{ font-family: {_TITULOS}; font-size: 20pt; font-weight: 700; }}
QLabel#cifra_grande {{ font-family: {_TITULOS}; font-size: 30pt; font-weight: 800; color: {_s.acento}; }}
QLabel#tenue {{ color: {_s.tenue}; }}
QLabel#icono_tarjeta {{ background: {_s.hundido}; border: 1px solid {_s.borde_oro}; border-radius: 22px; }}
QLabel#estado_grande {{ font-family: {_TITULOS}; font-size: 17pt; font-weight: 700; color: {_s.acento}; }}
QLabel#fase {{ background: {_s.hundido}; color: {_s.tenue}; border: 1px solid {_s.borde}; border-radius: 15px;
               min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px; font-weight: 700; }}
QLabel#fase[estado="actual"] {{ background: {_ORO}; color: {_s.sobre_acento}; border-color: {_s.borde_oro}; }}
QLabel#fase[estado="hecha"] {{ color: {OK}; border-color: #2c5f45; }}
QLabel#piso {{ background: {_s.hundido}; color: {_s.tenue}; border: 1px solid {_s.borde}; border-radius: 11px;
               padding: 3px 12px; font-weight: 600; font-size: 9pt; }}
QLabel#piso[estado="actual"] {{ background: {_ORO}; color: {_s.sobre_acento}; border-color: {_s.borde_oro}; }}
QLabel#piso[estado="hecha"] {{ color: {OK}; border-color: #2c5f45; }}
QFrame#premio {{ background: {_s.hundido}; border: 1px solid {_s.borde}; border-radius: 9px; min-width: 54px; }}
QFrame#premio:hover {{ border-color: {_s.borde_oro}; }}
QLabel#prob_premio {{ color: {_s.tenue}; font-size: 8.5pt; font-weight: 600; }}
QLabel#prob_premio[raro="true"] {{ color: {_s.acento}; }}
QLabel#prob_premio[siempre="true"] {{ color: {OK}; }}
QFrame#objeto_mini {{ background: {_s.hundido}; border: 1px solid {_s.borde}; border-radius: 9px; min-width: 56px; }}
QFrame#objeto_mini:hover {{ border-color: {_s.borde_oro}; }}
QLabel#cantidad_mini {{ color: {_s.acento}; font-weight: 700; font-size: 9pt; }}
QFrame#tarjeta_objeto {{ background: {_PANEL}; border: 1px solid {_s.borde}; border-radius: 12px; }}
QFrame#tarjeta_objeto:hover {{ border-color: {_s.borde_oro}; }}
QFrame#tarjeta_objeto[sin_nombre="true"] {{ border: 1px dashed {AVISO}; }}
QLabel#cantidad_objeto {{ font-family: {_TITULOS}; font-size: 15pt; font-weight: 700; color: {_s.acento}; }}
QLabel#foto_objeto {{ background: {_s.profundo}; border: 1px solid {_s.borde_oro}; border-radius: 10px; }}
QLabel#vista {{ background: {_s.profundo}; border: 1px solid {_s.borde}; border-radius: 6px; }}
QFrame#tarjeta {{ background: {_PANEL}; border: 1px solid {_s.borde}; border-radius: 10px; }}
QFrame#aviso {{ background: #3a2f17; border: 1px solid {AVISO}; border-radius: 10px; }}
QFrame#peligro {{ background: #3a1d1d; border: 1px solid {ERROR}; border-radius: 10px; }}
QGroupBox {{ background: {_PANEL}; border: 1px solid {_s.borde}; border-top: 1px solid {_s.borde_oro}; border-radius: 10px;
             margin-top: 14px; padding: 12px; }}
QGroupBox QWidget {{ background: transparent; }}
QGroupBox QLineEdit, QGroupBox QSpinBox, QGroupBox QComboBox, QGroupBox QListWidget {{ background: {_s.hundido}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 4px; color: {_s.acento}; font-family: {_TITULOS};
                    font-weight: 700; }}

/* ---- controles */
QPushButton {{ background: {_PANEL}; border: 1px solid {_s.borde}; border-radius: 7px; padding: 8px 16px; }}
QPushButton:hover {{ border-color: {_s.acento}; color: {_s.acento_claro}; }}
QPushButton:disabled {{ color: {DEBUG}; border-color: {_s.panel}; }}
QPushButton#primario {{ background: {_ORO}; color: {_s.sobre_acento}; border: 1px solid {_s.borde_oro}; font-weight: 700; }}
QPushButton#primario:hover {{ background: {_ORO_HOVER}; color: {_s.sobre_acento}; }}
QPushButton#primario:disabled {{ background: {_s.seleccion}; color: {_s.tenue}; }}
QPushButton#iniciar, QToolButton#iniciar {{ background: #2c5f45; border: 1px solid {OK}; font-weight: 700; }}
QPushButton#detener, QToolButton#detener {{ background: #5f2c2c; border: 1px solid {ERROR}; font-weight: 700; }}
QPushButton#pausar, QToolButton#pausar {{ background: #5f4f2c; border: 1px solid {AVISO}; font-weight: 700; }}
QToolButton#iniciar, QToolButton#detener, QToolButton#pausar {{ border-radius: 16px; padding: 8px 4px 6px 4px; }}
QToolButton#iniciar:hover, QToolButton#detener:hover, QToolButton#pausar:hover {{ border-width: 2px; }}
QToolButton#iniciar:disabled, QToolButton#detener:disabled, QToolButton#pausar:disabled {{
    background: {_s.panel}; border-color: {_s.borde}; color: {DEBUG}; }}
QFrame#cifra_mini {{ background: {_PANEL}; border: 1px solid {_s.borde}; border-radius: 12px; }}
QFrame#cifra_mini QLabel#cifra {{ font-size: 16pt; padding-left: 4px; }}
QLineEdit, QSpinBox, QComboBox, QTextEdit, QListWidget, QTableWidget {{
    background: {_s.hundido}; border: 1px solid {_s.borde}; border-radius: 6px; padding: 4px;
    selection-background-color: {_s.acento}; selection-color: {_s.sobre_acento}; }}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {_s.borde_oro}; }}
QComboBox QAbstractItemView {{ background: {_s.panel}; border: 1px solid {_s.borde_oro}; }}
QTextEdit#registro {{ font-family: 'Cascadia Mono', 'Consolas'; font-size: 9pt; }}
QHeaderView::section {{ background: {_s.panel}; color: {_s.tenue}; border: none; border-bottom: 1px solid {_s.borde_oro}; padding: 6px; }}
QTableWidget {{ gridline-color: {_s.borde}; alternate-background-color: {_s.panel}; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {_s.borde}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {_s.borde_oro}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {_s.borde}; border-radius: 4px; min-width: 30px; }}
QCheckBox::indicator {{ width: 15px; height: 15px; }}
QProgressBar {{ background: {_s.hundido}; border: 1px solid {_s.borde}; border-radius: 6px; text-align: center; height: 18px; }}
QProgressBar::chunk {{ background: {_ORO}; border-radius: 6px; }}

/* ---- inicio guiado */
QFrame#seccion {{ background: {_PANEL}; border: 1px solid {_s.borde}; border-top: 1px solid {_s.borde_oro}; border-radius: 12px; }}
QLabel#titulo_seccion {{ font-family: {_TITULOS}; font-size: 12.5pt; font-weight: 700; }}
QLabel#titulo_tarjeta {{ font-family: {_TITULOS}; font-size: 14pt; font-weight: 700; }}
QToolButton#paso {{ background: {_PANEL}; border: 1px solid {_s.borde}; border-radius: 14px; padding: 8px 6px 6px 6px;
                    color: {_s.tenue}; font-size: 9pt; }}
QToolButton#paso:hover {{ border-color: {_s.borde_oro}; color: {_s.texto}; }}
QToolButton#paso[estado="ok"] {{ border-color: #2c5f45; }}
QToolButton#paso[estado="falta"] {{ border-color: #8a6a2c; color: {_s.texto}; }}
QLabel#nombre_rueda {{ font-family: {_TITULOS}; font-size: 20pt; font-weight: 700; color: {_s.acento}; }}
QPushButton#flecha_rueda {{ background: {_s.hundido}; border: 1px solid {_s.borde_oro}; border-radius: 23px; padding: 0; }}
QPushButton#flecha_rueda:hover {{ background: {_SEL}; border-color: {_s.acento}; }}
QFrame#tarjeta_modo {{ background: {_PANEL}; border: 1px solid {_s.borde}; border-radius: 14px; }}
QFrame#tarjeta_modo:hover {{ border-color: {_s.borde_oro}; }}
QFrame#tarjeta_modo[seleccionada="true"] {{ border: 2px solid {_s.acento}; background: {_SEL}; }}
QScrollArea#area_pagina, QWidget#contenido_desplazable {{ background: transparent; }}
QFrame#tarjeta_pronto {{ background: transparent; border: 1px dashed {_s.borde}; border-radius: 14px; }}
QLabel#etiqueta_modo {{ color: {_s.tenue}; border: 1px solid {_s.borde}; border-radius: 11px; padding: 3px 10px; min-height: 16px; font-size: 8.5pt; }}
QLabel#etiqueta_modo[listo="true"] {{ color: {_s.sobre_acento}; background: {_s.acento}; border-color: {_s.borde_oro}; font-weight: 700; }}
QLabel#iniciales {{ background: {_s.borde}; border-radius: 20px; color: {_s.texto}; font-weight: 700; }}
QPushButton#chico {{ padding: 5px 10px; }}
QPushButton#desplegable {{ background: transparent; border: none; text-align: left; padding: 8px 2px; font-weight: 700;
                           font-size: 10.5pt; }}
QWidget#cuerpo_desplegable {{ background: transparent; }}
QPushButton#desplegable:hover, QPushButton#desplegable:checked {{ color: {_s.acento}; }}
QPushButton#chip {{ padding: 6px 14px; border-radius: 15px; }}
QPushButton#chip:checked {{ background: {_ORO}; color: {_s.sobre_acento}; border-color: {_s.borde_oro}; font-weight: 700; }}
QPushButton#empezar {{ background: {_ORO}; color: {_s.sobre_acento}; border: 2px solid {_s.borde_oro}; border-radius: 12px;
                       font-family: {_TITULOS}; font-size: 15pt; font-weight: 800; letter-spacing: 1px; }}
QPushButton#empezar:hover {{ background: {_ORO_HOVER}; color: {_s.sobre_acento}; }}
QPushButton#empezar:disabled {{ background: {_s.seleccion}; color: {_s.tenue}; border-color: {_s.borde}; }}
QPushButton#empezar[corriendo="true"] {{ background: #5f2c2c; color: {_s.texto}; border: 2px solid {ERROR}; }}
QProgressBar {{ background: {_s.hundido}; border: none; border-radius: 3px; }}
QProgressBar::chunk {{ background: {OK}; border-radius: 3px; }}

/* ---- galeria de personajes y equipos */
QFrame#tarjeta_pj {{ background: {_PANEL}; border: 1px solid {_s.borde}; border-radius: 12px; }}
QFrame#tarjeta_pj:hover {{ border-color: {_s.borde_oro}; }}
QFrame#tarjeta_pj[tengo="true"] {{ border: 2px solid {_s.acento}; background: {_SEL}; }}
QLabel#nombre_pj {{ font-weight: 700; }}
QLabel#foto_pj {{ background: {_s.profundo}; border-radius: 8px; }}
QFrame#tarjeta_equipo {{ background: {_PANEL}; border: 1px solid {_s.borde}; border-radius: 14px; }}
QFrame#tarjeta_equipo:hover {{ border-color: {_s.borde_oro}; }}

/* ---- pestanas */
QTabWidget::pane {{ border: 1px solid {_s.borde}; border-radius: 8px; top: -1px; background: {_s.fondo}; }}
QTabBar::tab {{ background: {_s.panel}; color: {_s.tenue}; padding: 8px 20px; border: 1px solid {_s.borde}; border-bottom: none;
               border-top-left-radius: 7px; border-top-right-radius: 7px; margin-right: 3px; font-family: {_TITULOS}; }}
QTabBar::tab:selected {{ color: {_s.acento}; background: {_s.fondo}; border-top: 2px solid {_s.acento}; }}
QTabBar::tab:hover {{ color: {_s.texto}; }}

/* ---- barra inferior */
QFrame#barra {{ background: {_s.lateral}; border-top: 1px solid {_s.borde_oro}; }}
QFrame#barra QLabel {{ color: {_s.tenue}; font-size: 9pt; }}
"""

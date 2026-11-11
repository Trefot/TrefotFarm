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
    moderno: bool = False
    claro: bool = False
    icono: str = ""  # adorno de temporada (Material Design Icons)
    saludo: str = ""
    fechas: tuple = field(default=())  # ((mes, dia_desde), (mes, dia_hasta)), puede cruzar de año


SKINS = {
    "taberna_viva": Skin(
        "taberna_viva", "Taberna · Luz de aventura",
        fondo="#191311", lateral="#130f0d", panel="#29201a", panel_alto="#3a2b20", borde="#544031",
        borde_oro="#99733e", texto="#f5e7cd", tenue="#bea88a", acento="#edbd69", acento_claro="#ffe0a0",
        sobre_acento="#2c1b0c", seleccion="#44311e", hundido="#1b1512", profundo="#100c0a",
        icono="mdi6.fireplace", saludo="Tu próxima aventura empieza en la taberna",
    ),
    "lumen_noche": Skin(
        "lumen_noche", "Lumen · Noche azul",
        fondo="#0b1120", lateral="#080d18", panel="#121c2d", panel_alto="#172339", borde="#26344b",
        borde_oro="#3b82f6", texto="#edf3ff", tenue="#9caec8", acento="#67a9ff", acento_claro="#91c0ff",
        sobre_acento="#071426", seleccion="#1b3353", hundido="#0c1525", profundo="#080f1c", moderno=True,
    ),
    "lumen_dia": Skin(
        "lumen_dia", "Lumen · Día claro",
        fondo="#f3f6fb", lateral="#ffffff", panel="#ffffff", panel_alto="#ffffff", borde="#d3deec",
        borde_oro="#2563eb", texto="#172a43", tenue="#536783", acento="#245ecb", acento_claro="#174ba9",
        sobre_acento="#ffffff", seleccion="#e6efff", hundido="#f8faff", profundo="#e5edf7", moderno=True, claro=True,
    ),
    "lumen_arcano": Skin(
        "lumen_arcano", "Lumen · Arcano",
        fondo="#100e21", lateral="#0c0a1a", panel="#1c1734", panel_alto="#231d43", borde="#3e345c",
        borde_oro="#9e79e8", texto="#f0eafd", tenue="#b1a1ce", acento="#ba99ff", acento_claro="#d3baff",
        sobre_acento="#180c2d", seleccion="#342452", hundido="#120e25", profundo="#090714", moderno=True,
    ),
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
NORMAL = "taberna_viva"


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
if SKIN.moderno:
    FUENTE_TITULOS = "Segoe UI"
    FUENTE_MARCA = "Segoe UI"

FONDO = SKIN.fondo
LATERAL = SKIN.lateral
PANEL = SKIN.panel
BORDE = SKIN.borde
TEXTO = SKIN.texto
TENUE = SKIN.tenue
ACENTO = SKIN.acento
SOBRE_ACENTO = SKIN.sobre_acento
OK = "#18764c" if SKIN.claro else "#4cc38a"
AVISO = "#93610b" if SKIN.claro else "#e6b84c"
ERROR = "#c43d4c" if SKIN.claro else "#ef6461"
DEBUG = "#66758c" if SKIN.claro else "#6b7186"

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
QLabel#etapa {{ background: {_s.hundido}; color: {_s.tenue}; border: 1px solid {_s.borde}; border-radius: 13px;
                padding: 4px 14px; font-weight: 600; }}
QLabel#etapa[estado="actual"] {{ background: {_ORO}; color: {_s.sobre_acento}; border-color: {_s.borde_oro}; }}
QLabel#etapa[estado="hecha"] {{ color: {OK}; border-color: #2c5f45; }}
QLabel#piso {{ background: {_s.hundido}; color: {_s.tenue}; border: 1px solid {_s.borde}; border-radius: 11px;
               padding: 3px 12px; font-weight: 600; font-size: 9pt; }}
QLabel#piso[estado="actual"] {{ background: {_ORO}; color: {_s.sobre_acento}; border-color: {_s.borde_oro}; }}
QLabel#piso[estado="hecha"] {{ color: {OK}; border-color: #2c5f45; }}
QFrame#premio_mini {{ background: {_s.hundido}; border: 1px solid {_s.borde}; border-radius: 7px; min-width: 42px; }}
QFrame#raya {{ color: {_s.borde}; }}
QFrame#premio {{ background: {_s.hundido}; border: 1px solid {_s.borde}; border-radius: 9px; min-width: 54px; }}
QFrame#premio:hover {{ border-color: {_s.borde_oro}; }}
QLabel#prob_premio {{ color: {_s.tenue}; font-size: 8.5pt; font-weight: 600; }}
QLabel#prob_premio[raro="true"] {{ color: {_s.acento}; }}
QLabel#prob_premio[siempre="true"] {{ color: {OK}; }}
QFrame#tarea_plan {{ background: {_s.hundido}; border: 1px solid {_s.borde}; border-radius: 9px; }}
QFrame#tarea_plan[estado="actual"] {{ border: 2px solid {_s.acento}; background: {_SEL}; }}
QFrame#tarea_plan[estado="hecha"] {{ border-color: #2c5f45; }}
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
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 15px; height: 15px; border: 1px solid {_s.borde_oro}; border-radius: 4px; background: {_s.hundido}; }}
QCheckBox::indicator:hover {{ border-color: {_s.acento}; }}
QCheckBox::indicator:checked {{ background: {_ORO}; border-color: {_s.acento}; }}
QCheckBox::indicator:disabled {{ border-color: {_s.borde}; }}
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
QTabBar::tab {{ background: {_s.panel}; color: {_s.tenue}; padding: 8px 26px; border: 1px solid {_s.borde}; border-bottom: none;
               border-top-left-radius: 7px; border-top-right-radius: 7px; margin-right: 3px; font-family: {_TITULOS}; }}
QTabBar::tab:selected {{ color: {_s.acento}; background: {_s.fondo}; border-top: 2px solid {_s.acento}; }}
QTabBar::tab:hover {{ color: {_s.texto}; }}

/* ---- barra inferior */
QFrame#barra {{ background: {_s.lateral}; border-top: 1px solid {_s.borde_oro}; }}
QFrame#barra QLabel {{ color: {_s.tenue}; font-size: 9pt; }}
"""

# Los temas nuevos comparten una jerarquia visual sencilla y superficies planas.
# El tema original y los de temporada conservan su apariencia.
if SKIN.moderno:
    HOJA += f"""
    QWidget {{ font-family: 'Segoe UI'; font-size: 10pt; }}
    QFrame#lateral {{ background: {_s.lateral}; border-right: 1px solid {_s.borde}; }}
    QLabel#marca {{ font-family: 'Segoe UI'; color: {_s.texto}; font-size: 11pt; letter-spacing: 1px; }}
    QToolButton#menu {{ min-width: 132px; padding: 12px 8px; border-radius: 8px; font-size: 10pt; text-align: left; }}
    QToolButton#menu:checked {{ background: {_s.seleccion}; color: {_s.acento}; border: 1px solid {_s.borde}; }}
    QFrame#separador_oro {{ background: {_s.borde}; }}
    QLabel#titulo_pagina {{ font-size: 22pt; color: {_s.texto}; font-weight: 700; }}
    QLabel#nombre_rueda {{ font-size: 22pt; color: {_s.texto}; }}
    QLabel#estado_grande {{ color: {_s.acento}; font-size: 18pt; }}
    QFrame#seccion, QFrame#tarjeta, QFrame#tarjeta_objeto, QFrame#tarjeta_pj,
    QFrame#tarjeta_equipo, QFrame#tarjeta_modo {{ background: {_s.panel}; border: 1px solid {_s.borde}; border-radius: 14px; }}
    QFrame#tarjeta_pj[tengo="true"], QFrame#tarjeta_modo[seleccionada="true"] {{ background: {_s.seleccion}; border: 2px solid {_s.acento}; }}
    QFrame#cifra_mini {{ background: {_s.panel}; border: 1px solid {_s.borde}; border-radius: 12px; }}
    QFrame#cifra_mini QLabel#cifra {{ font-family: 'Segoe UI'; font-size: 21pt; color: {_s.texto}; }}
    QPushButton {{ background: {_s.panel}; border-radius: 8px; border: 1px solid {_s.borde}; padding: 9px 14px; }}
    QPushButton:focus, QToolButton:focus {{ border: 2px solid {_s.acento}; }}
    QPushButton#primario, QPushButton#empezar {{ background: {_s.acento}; color: {_s.sobre_acento}; border: 1px solid {_s.acento}; }}
    QPushButton#primario:hover, QPushButton#empezar:hover {{ background: {_s.acento_claro}; color: {_s.sobre_acento}; }}
    QPushButton#chip {{ border-radius: 9px; padding: 7px 14px; }}
    QPushButton#chip:checked {{ background: {_s.acento}; border: 1px solid {_s.acento}; color: {_s.sobre_acento}; }}
    QLabel#fase[estado="actual"], QLabel#etapa[estado="actual"], QLabel#piso[estado="actual"] {{ background: {_s.acento}; color: {_s.sobre_acento}; }}
    QLineEdit, QSpinBox, QComboBox, QTextEdit, QListWidget, QTableWidget {{ background: {_s.hundido}; color: {_s.texto}; border: 1px solid {_s.borde}; border-radius: 8px; padding: 6px; }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus {{ border: 1px solid {_s.acento}; }}
    QTabWidget::pane {{ background: {_s.panel}; border: 1px solid {_s.borde}; border-radius: 10px; }}
    QTabBar::tab {{ font-family: 'Segoe UI'; background: transparent; padding: 10px 18px; color: {_s.tenue}; border: none; border-bottom: 2px solid transparent; }}
    QTabBar::tab:selected {{ background: {_s.seleccion}; color: {_s.acento}; border-top: none; border-bottom: 2px solid {_s.acento}; }}
    QFrame#barra {{ background: {_s.lateral}; border-top: 1px solid {_s.borde}; }}
    """
    if SKIN.claro:
        HOJA += f"""
        QPushButton#iniciar, QToolButton#iniciar {{ background: #e5f5ec; color: {OK}; border-color: #a7d4ba; }}
        QPushButton#pausar, QToolButton#pausar {{ background: #fff4d9; color: {AVISO}; border-color: #e4c478; }}
        QPushButton#detener, QToolButton#detener {{ background: #ffebee; color: {ERROR}; border-color: #e8b2bc; }}
        QToolButton#iniciar:disabled, QToolButton#pausar:disabled, QToolButton#detener:disabled {{ background: {_s.hundido}; color: {DEBUG}; border-color: {_s.borde}; }}
        QFrame#aviso {{ background: #fff4d9; border-color: #e4c478; }}
        QFrame#peligro {{ background: #ffebee; border-color: #e8b2bc; }}
        QToolButton#paso[estado="falta"] {{ border-color: {_s.borde}; color: {_s.texto}; }}
        """

# Arquitectura visual por tareas, compartida por los temas.
HOJA += f"""
QFrame#contenido_card {{ background: {_s.panel}; border: 1px solid {_s.borde}; border-radius: 16px; }}
QFrame#hero {{ background: {_s.seleccion}; border: 1px solid {_s.borde}; border-radius: 18px; }}
QLabel#titulo_card {{ font-size: 15pt; font-weight: 600; color: {_s.texto}; }}
QLabel#titulo_hero {{ font-size: 24pt; font-weight: 700; color: {_s.texto}; }}
QLabel#eyebrow {{ color: {_s.tenue}; font-size: 9pt; font-weight: 600; padding: 8px 2px; }}
QLabel#badge_listo {{ color: {OK}; background: {_s.hundido}; padding: 5px 8px; border-radius: 8px; font-size: 9pt; }}
QLabel#badge_pronto {{ color: {_s.tenue}; background: {_s.hundido}; padding: 5px 8px; border-radius: 8px; font-size: 9pt; }}
QPushButton#accion_card {{ text-align: left; color: {_s.acento}; padding: 11px 12px; }}
QToolButton#menu {{ min-width: 164px; padding: 10px 8px; text-align: left; font-size: 10pt; }}
QProgressBar {{ border: 1px solid {_s.borde}; border-radius: 6px; text-align: center; min-height: 18px; }}
QProgressBar::chunk {{ background: {_s.acento}; border-radius: 5px; }}
"""

if SKIN.id == "taberna_viva":
    HOJA += """
    QWidget { font-size: 10pt; }
    QLabel#titulo_pagina { font-family: 'Cinzel', 'Georgia'; font-size: 23pt; color: #f6d797; }
    QLabel#titulo_card, QLabel#titulo_hero { font-family: 'Cinzel', 'Georgia'; color: #f5dcac; }
    QLabel#titulo_card { font-size: 15pt; }
    QLabel#titulo_hero { font-size: 27pt; }
    QLabel#eyebrow { color: #d3ab68; letter-spacing: 1px; }
    QFrame#lateral { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #130e0b,stop:1 #251b14); border-right: 1px solid #715331; }
    QLabel#marca { color: #f0ca82; font-size: 18pt; }
    QToolButton#menu { min-width: 164px; border: 1px solid transparent; border-radius: 6px; padding: 9px 8px; color: #cbb493; }
    QToolButton#menu:hover { background: #3c2b1d; color: #ffe1a4; border: 1px solid #705132; }
    QToolButton#menu:checked { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #664324,stop:1 #302117); border: 1px solid #b68b48; color: #ffe2a8; }
    QFrame#contenido_card, QFrame#seccion, QFrame#tarjeta { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #32251b,stop:1 #241b15); border: 1px solid #634b33; border-radius: 10px; }
    QFrame#contenido_card:hover { border-color: #ba8c4c; }
    QFrame#escena_aventura, QFrame#aventura_card { background: transparent; border: none; }
    QFrame#escena_aventura QLabel, QFrame#aventura_card QLabel { background: transparent; }
    QLabel#rotulo_aventura { color: #e9c989; font-size: 10pt; letter-spacing: 2px; }
    QLabel#detalle_aventura { color: #e1cdb0; font-size: 11pt; }
    QLabel#nota_pergamino { background: #c8aa76; color: #392619; padding: 16px; border: 1px solid #e2c18b; border-radius: 5px; }
    QPushButton#primario, QPushButton#empezar { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #f2d18d,stop:1 #b8843c); color: #2c1a0b; border: 1px solid #f9d99b; padding: 12px 18px; font-weight: 700; border-radius: 6px; }
    QPushButton#primario:hover { background: #ffe1a1; }
    QPushButton#accion_card { color: #f1ce8b; background: rgba(50,37,27,215); border: 1px solid #856239; border-radius: 5px; }
    QPushButton#accion_card:hover { background: #5a3f23; border-color: #e2b96e; }
    QLabel#badge_listo { color: #c5dda4; background: #283022; border: 1px solid #52603a; }
    QLabel#badge_pronto { background: #362b23; color: #c7af8b; }
    QFrame#tarjeta QLabel#cifra { color: #efd29b; }
    """

# Categorias visibles y controles legibles en la ventana definitiva.
HOJA += f"""
QTabBar#categorias_contenido::tab {{ font-family: 'Segoe UI'; font-size: 11pt; font-weight: 600; padding: 10px 24px; color: {_s.tenue}; background: transparent; border: none; border-bottom: 2px solid {_s.borde}; }}
QTabBar#categorias_contenido::tab:selected {{ color: {_s.acento}; border-bottom: 2px solid {_s.acento}; background: {_s.seleccion}; }}
QTabBar#categorias_contenido::tab:hover {{ color: {_s.texto}; }}
QFrame#escena_destino QLabel#tenue {{ font-size: 10.5pt; }}
QFrame#escena_destino QLabel#detalle_aventura {{ font-size: 11pt; }}
QFrame#escena_destino QComboBox {{ font-size: 11pt; padding: 7px 12px; }}
QPushButton#consultar_destino {{ background: {_s.hundido}; color: {_s.tenue}; border: 1px solid {_s.tenue}; border-radius: 6px; padding: 12px 18px; }}
QPushButton#consultar_destino:hover {{ background: {_s.panel}; color: {_s.texto}; }}
"""

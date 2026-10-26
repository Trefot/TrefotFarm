"""Estilo visual de la interfaz (tema oscuro)."""

FONDO = "#14161c"
LATERAL = "#0f1116"
PANEL = "#1d2029"
BORDE = "#2c3040"
TEXTO = "#e6e8ef"
TENUE = "#8b90a3"
ACENTO = "#e0a526"  # dorado
OK = "#4cc38a"
AVISO = "#e6b84c"
ERROR = "#ef6461"
DEBUG = "#6b7186"

COLOR_NIVEL = {"info": TEXTO, "ok": OK, "aviso": AVISO, "error": ERROR, "debug": DEBUG}

HOJA = f"""
QWidget {{ background: {FONDO}; color: {TEXTO}; font-family: 'Segoe UI'; font-size: 10pt; }}
QLabel, QCheckBox {{ background: transparent; }}

/* ---- menu lateral */
QFrame#lateral {{ background: {LATERAL}; border-right: 1px solid {BORDE}; }}
QLabel#marca {{ font-size: 15pt; font-weight: 800; color: {ACENTO}; padding: 6px 4px 0 4px; }}
QPushButton#menu {{ font-family: 'Segoe UI Symbol', 'Segoe UI'; text-align: left; padding: 10px 14px; border: none; border-radius: 8px;
                    color: {TENUE}; font-size: 10.5pt; background: transparent; }}
QPushButton#menu:hover {{ background: {PANEL}; color: {TEXTO}; }}
QPushButton#menu:checked {{ background: {PANEL}; color: {ACENTO}; font-weight: 600; border-left: 3px solid {ACENTO}; }}
QPushButton#menu:disabled {{ color: #3a3f50; }}
QFrame#lateral QLabel#insignia {{ background: {ERROR}; color: white; border-radius: 8px; padding: 1px 7px; font-size: 8pt; font-weight: 700; }}

/* ---- paginas */
QLabel#titulo_pagina {{ font-size: 18pt; font-weight: 700; }}
QLabel#cifra {{ font-size: 20pt; font-weight: 700; }}
QLabel#cifra_grande {{ font-size: 30pt; font-weight: 800; color: {ACENTO}; }}
QLabel#tenue {{ color: {TENUE}; }}
QLabel#vista {{ background: #0b0c10; border: 1px solid {BORDE}; border-radius: 6px; }}
QFrame#tarjeta {{ background: {PANEL}; border: 1px solid {BORDE}; border-radius: 10px; }}
QFrame#aviso {{ background: #3a2f17; border: 1px solid {AVISO}; border-radius: 10px; }}
QFrame#peligro {{ background: #3a1d1d; border: 1px solid {ERROR}; border-radius: 10px; }}
QGroupBox {{ background: {PANEL}; border: 1px solid {BORDE}; border-radius: 10px; margin-top: 14px; padding: 12px; }}
QGroupBox QWidget {{ background: transparent; }}
QGroupBox QLineEdit, QGroupBox QSpinBox, QGroupBox QComboBox, QGroupBox QListWidget {{ background: #101218; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 4px; color: {ACENTO}; font-weight: 600; }}

/* ---- controles */
QPushButton {{ background: {PANEL}; border: 1px solid {BORDE}; border-radius: 7px; padding: 8px 16px; }}
QPushButton:hover {{ border-color: {ACENTO}; }}
QPushButton:disabled {{ color: {DEBUG}; border-color: {PANEL}; }}
QPushButton#primario {{ background: {ACENTO}; color: #1a1406; border: none; font-weight: 700; }}
QPushButton#primario:hover {{ background: #f0b63a; }}
QPushButton#primario:disabled {{ background: #5a4a26; color: #8d7c55; }}
QPushButton#iniciar {{ background: #2c5f45; border-color: {OK}; font-weight: 700; }}
QPushButton#detener {{ background: #5f2c2c; border-color: {ERROR}; font-weight: 700; }}
QPushButton#pausar {{ background: #5f4f2c; border-color: {AVISO}; font-weight: 700; }}
QLineEdit, QSpinBox, QComboBox, QTextEdit, QListWidget, QTableWidget {{
    background: #101218; border: 1px solid {BORDE}; border-radius: 6px; padding: 4px; selection-background-color: {ACENTO}; }}
QTextEdit#registro {{ font-family: 'Cascadia Mono', 'Consolas'; font-size: 9pt; }}
QHeaderView::section {{ background: {PANEL}; color: {TENUE}; border: none; border-bottom: 1px solid {BORDE}; padding: 6px; }}
QTableWidget {{ gridline-color: {BORDE}; }}
QScrollArea {{ border: none; }}
QCheckBox::indicator {{ width: 15px; height: 15px; }}
QProgressBar {{ background: #101218; border: 1px solid {BORDE}; border-radius: 6px; text-align: center; height: 18px; }}
QProgressBar::chunk {{ background: {ACENTO}; border-radius: 6px; }}

/* ---- barra inferior */
QFrame#barra {{ background: {LATERAL}; border-top: 1px solid {BORDE}; }}
QFrame#barra QLabel {{ color: {TENUE}; font-size: 9pt; }}
"""

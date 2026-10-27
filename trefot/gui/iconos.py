"""Iconos de la interfaz (Material Design Icons via qtawesome) e imagenes redondeadas.

Si qtawesome no esta instalado la interfaz sigue funcionando, solo que sin iconos.
"""

from pathlib import Path

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QIcon, QPainter, QPainterPath, QPixmap

from trefot.gui import tema

try:
    import qtawesome as qta
except ImportError:  # pragma: no cover - solo si falta la dependencia
    qta = None

# Nombre logico -> icono de Material Design Icons (https://pictogrammers.com/library/mdi/)
NOMBRES = {
    "inicio": "mdi6.home-variant",
    "farmear": "mdi6.sword-cross",
    "capturas": "mdi6.camera",
    "personajes": "mdi6.account-group",
    "equipos": "mdi6.shield-account",
    "historial": "mdi6.chart-line",
    "recompensas": "mdi6.treasure-chest",
    "ajustes": "mdi6.cog",
    "ayuda": "mdi6.help-circle-outline",
    "juego": "mdi6.gamepad-variant",
    "ventana": "mdi6.monitor-screenshot",
    "equipo": "mdi6.account-multiple-check",
    "cartas": "mdi6.cards",
    "jugar": "mdi6.play",
    "pausa": "mdi6.pause",
    "detener": "mdi6.stop",
    "ok": "mdi6.check-circle",
    "falta": "mdi6.alert-circle",
    "error": "mdi6.close-circle",
    "reloj": "mdi6.timer-outline",
    "trofeo": "mdi6.trophy",
    "oro": "mdi6.cash-multiple",
    "pocion": "mdi6.flask",
    "candado": "mdi6.lock-outline",
    "actualizar": "mdi6.update",
    "buscar": "mdi6.magnify",
    "flecha": "mdi6.arrow-right",
    "derrota": "mdi6.skull-outline",
    "reinicio": "mdi6.restart",
    "tasa": "mdi6.bullseye-arrow",
    "objetos": "mdi6.package-variant-closed",
    "distintos": "mdi6.diamond-stone",
    "sesiones": "mdi6.calendar-check",
    "rayo": "mdi6.lightning-bolt",
    "registro": "mdi6.script-text-outline",
    "carpeta": "mdi6.folder-open-outline",
    "foto": "mdi6.image-outline",
    "aspecto": "mdi6.palette-outline",
    "movil": "mdi6.cellphone-message",
    "teclado": "mdi6.keyboard-outline",
    "admin": "mdi6.shield-crown-outline",
    "github": "mdi6.github",
    "guardar": "mdi6.content-save-outline",
}


def icono(nombre: str, color: str | None = None, color_activo: str | None = None) -> QIcon:
    if qta is None:
        return QIcon()
    color = color or tema.TEXTO
    opciones = {"color": color}
    if color_activo:
        opciones.update(color_on=color_activo, color_active=color_activo)
    try:
        return qta.icon(NOMBRES.get(nombre, nombre), **opciones)
    except Exception:  # un nombre de icono que no existe no debe tumbar la interfaz
        return QIcon()


def pixmap(nombre: str, tam: int = 20, color: str | None = None) -> QPixmap:
    ic = icono(nombre, color)
    return ic.pixmap(tam, tam) if not ic.isNull() else QPixmap()


def redondo(ruta: Path | str | None, tam: int, borde: str | None = None) -> QPixmap | None:
    """La imagen recortada en circulo (para retratos y emblemas). None si no existe."""
    if not ruta or not Path(ruta).is_file():
        return None
    original = QPixmap(str(ruta))
    if original.isNull():
        return None
    original = original.scaled(tam, tam, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    resultado = QPixmap(tam, tam)
    resultado.fill(Qt.transparent)
    p = QPainter(resultado)
    p.setRenderHint(QPainter.Antialiasing)
    camino = QPainterPath()
    camino.addEllipse(QRectF(1, 1, tam - 2, tam - 2))
    p.setClipPath(camino)
    p.drawPixmap((tam - original.width()) // 2, 0, original)
    p.setClipping(False)
    if borde:
        from PyQt5.QtGui import QColor, QPen

        p.setPen(QPen(QColor(borde), 2))
        p.drawEllipse(QRectF(1, 1, tam - 2, tam - 2))
    p.end()
    return resultado

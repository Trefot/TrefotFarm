"""Imagenes propias en lugar de las ajenas (pedido del usuario, 2026-11-22).

145 imagenes de assets/imagenes eran copia exacta de las ajenas (lumen/datos/imagenes_ajenas.txt).
Mientras se farmea, cada vez que una de ellas se reconoce en la pantalla del juego con mucha seguridad, se recorta
ese mismo trozo de la pantalla y se guarda como imagen propia (capturas/propias/). El Lumen del administrador las
sube a la base de todos (assets/propias/) y, desde entonces, Plantilla usa la propia en vez de la ajena.
Cuando todas tengan la suya, las ajenas se borran con su credito y su licencia.

El recorte se valida solo: es el trozo que coincidio con la ajena por encima de UMBRAL, del mismo tamano.
"""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

from lumen.rutas import ASSETS, CAPTURAS, IMAGENES

LISTA = Path(__file__).resolve().parent / "datos" / "imagenes_ajenas.txt"
CARPETA_REPO = ASSETS / "propias"  # las publicadas (llegan a todos con las actualizaciones)
CARPETA_LOCAL = CAPTURAS / "propias"  # las recortadas en este PC, a la espera de publicarse
UMBRAL = 0.85  # coincidencia minima con la ajena para recortar (el bot ya actua con 0,7-0,8)
CONFIRMAR = 0.97  # el segundo recorte tiene que parecerse tanto al primero (no un fotograma de una animacion)
SEPARACION_S = 10.0  # y salir al menos tanto despues
DIF_COLOR = 12.0  # y con el mismo color medio (0-255 por canal)
ALTO_MIN, ANCHO_MIN = 900, 500  # solo capturas de pantalla completas (no celdas ni recortes)

activo = False  # el motor lo enciende mientras corre un modo (las pruebas y la interfaz no recortan nada)
_lock = threading.Lock()
_lista: frozenset[str] | None = None
_hechas: set[str] = set()  # ya guardadas en esta sesion (no repetir la escritura en cada fotograma)
_candidatos: dict[str, tuple[float, np.ndarray]] = {}  # primer recorte de cada una (cuando, imagen), en memoria


def ajenas() -> frozenset[str]:
    """Rutas (relativas a assets/imagenes, con /) de las imagenes que son ajenas."""
    global _lista
    if _lista is None:
        try:
            lineas = LISTA.read_text(encoding="utf-8").splitlines()
        except OSError:
            lineas = []
        _lista = frozenset(l.strip() for l in lineas if l.strip() and not l.startswith("#"))
    return _lista


def relativa(ruta: Path) -> str | None:
    """'demons/accept.png' si la ruta esta dentro de assets/imagenes; si no, None."""
    try:
        return Path(ruta).resolve().relative_to(IMAGENES.resolve()).as_posix()
    except (ValueError, OSError):
        return None


def _nombre_propio(rel: str) -> str:
    return str(Path(rel).with_suffix(".png").as_posix())  # siempre PNG (sin perdida), aunque la original sea .jpg


def ruta_repo(rel: str) -> Path:
    return CARPETA_REPO / _nombre_propio(rel)


def ruta_local(rel: str) -> Path:
    return CARPETA_LOCAL / _nombre_propio(rel)


def preferida(ruta: Path) -> Path:
    """La imagen propia publicada si la hay; si no, la de siempre."""
    rel = relativa(ruta)
    if rel is None or rel not in ajenas():
        return Path(ruta)
    propia = ruta_repo(rel)
    return propia if propia.is_file() else Path(ruta)


def anotar(ruta: Path, pantalla, rect, valor: float) -> bool:
    """Una imagen ajenas acaba de reconocerse: guarda ese trozo de la pantalla como propia. True si guardo."""
    if not activo or valor < UMBRAL or pantalla is None or getattr(pantalla, "ndim", 0) != 3:
        return False
    if pantalla.shape[0] < ALTO_MIN or pantalla.shape[1] < ANCHO_MIN:
        return False
    rel = relativa(ruta)
    if rel is None or rel not in ajenas() or rel in _hechas:
        return False
    if ruta_repo(rel).is_file() or ruta_local(rel).is_file():
        _hechas.add(rel)
        return False
    x, y, w, h = (int(v) for v in rect)
    recorte = np.ascontiguousarray(pantalla[y:y + h, x:x + w])
    if recorte.shape[:2] != (h, w) or float(recorte.std()) < 3:  # fuera de la pantalla o plano
        return False
    import time

    import cv2

    from lumen.vision import guardar_imagen

    ahora = time.monotonic()
    with _lock:
        if rel in _hechas:
            return False
        previo = _candidatos.get(rel)
        if previo is None or previo[1].shape != recorte.shape:
            _candidatos[rel] = (ahora, recorte.copy())
            return False
        if ahora - previo[0] < SEPARACION_S:
            return False
        parecido = float(cv2.matchTemplate(recorte, previo[1], cv2.TM_CCOEFF_NORMED).max())
        # La comparacion de forma no ve el brillo: la pantalla oscurecida de "Auto Repeat" daba igual que la limpia.
        dif_color = float(np.abs(recorte.reshape(-1, 3).mean(0) - previo[1].reshape(-1, 3).mean(0)).max())
        if parecido < CONFIRMAR or dif_color > DIF_COLOR:  # distinto del primero: este pasa a ser el candidato
            _candidatos[rel] = (ahora, recorte.copy())
            return False
        try:
            guardar_imagen(ruta_local(rel), recorte)
        except Exception:
            return False
        _hechas.add(rel)
        _candidatos.pop(rel, None)
    return True


def pendientes() -> list[str]:
    """Recortadas en este PC que aun no estan en la base de todos."""
    if not CARPETA_LOCAL.is_dir():
        return []
    salida = []
    lista = ajenas()
    for rel in lista:
        if ruta_local(rel).is_file() and not ruta_repo(rel).is_file():
            salida.append(rel)
    return sorted(salida)


def progreso() -> tuple[int, int]:
    """(cuantas ajenas ya tienen propia publicada o recortada aqui, cuantas son en total)."""
    lista = ajenas()
    hechas = sum(1 for rel in lista if ruta_repo(rel).is_file() or ruta_local(rel).is_file())
    return hechas, len(lista)


def preparar_copia(copia: Path) -> list[str]:
    """Para publicar.subir_imagenes_propias: copia las pendientes a assets/propias de la copia del repositorio."""
    import shutil

    hechas = []
    for rel in pendientes():
        destino = Path(copia) / "assets" / "propias" / _nombre_propio(rel)
        if destino.is_file():
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ruta_local(rel), destino)
        original = Path(copia) / "assets" / "imagenes" / rel
        if original.is_file():  # ya tiene la suya: la ajena se borra (Plantilla usa la propia)
            original.unlink()
        hechas.append(rel)
    return hechas

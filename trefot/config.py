"""Configuracion persistente en config.yaml (se crea sola con los valores por defecto)."""

import threading

import yaml

from trefot.rutas import CONFIG

POR_DEFECTO = {
    "titulo_ventana": "7DS",  # titulo exacto de la ventana del juego (Japon: "グラクロ")
    "ntfy_canal": "",  # canal de ntfy.sh para avisos al movil (vacio = desactivado)
    "minutos_atasco": 8,  # minutos sin cambios antes de avisar que el bot esta trabado
    "tecla_pausa": "f9",
    "tecla_detener": "f10",
    "fps_vista_previa": 3,
    "ultimo_modo": "perros_piso4",
    "opciones_modos": {},
}

_lock = threading.Lock()
_datos: dict | None = None


def _cargar() -> dict:
    datos = dict(POR_DEFECTO)
    if CONFIG.is_file():
        with CONFIG.open(encoding="utf-8") as f:
            leidos = yaml.safe_load(f) or {}
        datos.update(leidos)
    return datos


def obtener(clave: str, defecto=None):
    global _datos
    with _lock:
        if _datos is None:
            _datos = _cargar()
        return _datos.get(clave, POR_DEFECTO.get(clave, defecto))


def guardar(cambios: dict) -> None:
    global _datos
    with _lock:
        if _datos is None:
            _datos = _cargar()
        _datos.update(cambios)
        with CONFIG.open("w", encoding="utf-8") as f:
            yaml.safe_dump(_datos, f, allow_unicode=True, sort_keys=False)


def todo() -> dict:
    obtener("titulo_ventana")
    with _lock:
        return dict(_datos)

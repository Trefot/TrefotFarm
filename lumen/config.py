"""Configuracion persistente en config.yaml (se crea sola con los valores por defecto)."""

import threading

import yaml

from lumen.rutas import CONFIG

POR_DEFECTO = {
    "titulo_ventana": "7DS",  # titulo exacto de la ventana del juego (Japon: "グラクロ")
    "ntfy_canal": "",  # canal de ntfy.sh para avisos al movil (vacio = desactivado)
    "ntfy_ordenes": False,  # aceptar ordenes (estado, pausar, captura...) escritas en ese canal
    "minutos_atasco": 8,  # minutos sin cambios antes de avisar que el bot esta trabado
    "tecla_pausa": "f9",
    "tecla_detener": "f10",
    "ultimo_modo": "perros_piso4",
    "modo_admin": False,  # muestra Capturas y el Editor de personajes
    "skin": "auto",
    "asistente_visto": False,  # el asistente de primera vez ya salio
    "acceso_ofrecido": False,  # ya se pregunto si crear los accesos directos  # "auto" = segun la fecha; o el id de una skin de gui/tema.py
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
        if datos.get("limpieza_victorias", 0) < 2:
            _limpiar_victorias(datos)
            with CONFIG.open("w", encoding="utf-8") as f:
                yaml.safe_dump(datos, f, allow_unicode=True, sort_keys=False)
    return datos


def _limpiar_victorias(datos: dict) -> None:
    """La prueba rapida dejaba guardada 1 victoria en cada modo (hasta la 0.7.1) y los Floor 1-3 paraban tras un
    piso. Se borra al cargar, antes de que ninguna pagina lo lea (en la 0.7.3 se hacia en Inicio y la pagina
    Farmear ya lo habia cargado). Los Floor 1-3 vuelven a su valor por defecto: una pasada."""
    ya_limpio = datos.get("victorias_de_prueba_limpias")  # la limpieza de la 0.7.3 (solo los otros modos se respetan)
    opciones = {}
    for modo, o in (datos.get("opciones_modos") or {}).items():
        o = dict(o or {})
        if o.get("victorias") == 1 and (modo.endswith("_pisos1a3") or not ya_limpio):
            o.pop("victorias")
        opciones[modo] = o
    datos["opciones_modos"] = opciones
    datos["limpieza_victorias"] = 2


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

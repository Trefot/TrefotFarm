"""Textos para entender un fallo desde el movil: errores, atascos y el informe de la prueba rapida.

Todo es texto plano que se puede copiar de la app ntfy y pegar tal cual a quien mantiene el bot.
Los ultimos pasos del bot se guardan aqui (``anotar``, lo llama el puente con cada linea del registro).
"""

import time
import traceback
from collections import deque
from pathlib import Path

import lumen

PASOS = 12  # lineas del registro que acompanan a un error o un atasco
_recientes: deque[str] = deque(maxlen=PASOS)


def anotar(mensaje: str, nivel: str) -> None:
    _recientes.append(f"{time.strftime('%H:%M:%S')} [{nivel}] {mensaje}")


def recientes() -> list[str]:
    return list(_recientes)


def donde(error: BaseException) -> str:
    """El archivo y la linea del bot donde salto el error (la ultima de lumen/ en la traza)."""
    marcos = [m for m in traceback.extract_tb(error.__traceback__) if "lumen" in Path(m.filename).parts]
    if not marcos:
        return ""
    m = marcos[-1]
    return f"{Path(m.filename).name}:{m.lineno} en {m.name}"


def resumen_error(error: BaseException) -> str:
    """Una linea: el error y donde salto (para el informe de la prueba)."""
    lugar = donde(error)
    return f"{type(error).__name__}: {error}" + (f" ({lugar})" if lugar else "")


def _cabecera(titulo: str) -> str:
    return f"Lumen Farm {lumen.__version__} · {titulo} · {time.strftime('%d/%m %H:%M')}"


def texto_error(modo, error: BaseException) -> str:
    lineas = [_cabecera("ERROR"),
              f"Modo: {getattr(modo, 'nombre', '?')} ({getattr(modo, 'id', '?')}) · estado: {getattr(modo, 'estado', '?')}",
              f"Error: {type(error).__name__}: {error}"]
    if donde(error):
        lineas.append(f"En: {donde(error)}")
    lineas += ["Últimos pasos:", *recientes()]
    return "\n".join(lineas)


def texto_atasco(modo, minutos: float) -> str:
    return "\n".join([_cabecera("ATASCADO"),
                      f"Modo: {getattr(modo, 'nombre', '?')} ({getattr(modo, 'id', '?')}) · estado: {getattr(modo, 'estado', '?')}",
                      f"Sin cambios desde hace {minutos:.0f} min.", "Últimos pasos:", *recientes()])


# ------------------------------------------------------------------ prueba rapida
MARCAS = {"ok": "✓", "fallo": "✗", "sin_victoria": "✗", "no_empezo": "–", "saltada": "–", "detenida": "■"}


def _tiempo(segundos: float) -> str:
    m, s = divmod(int(segundos), 60)
    return f"{m // 60}:{m % 60:02d}:{s:02d}" if m >= 60 else f"{m}:{s:02d}"


def texto_prueba(resultados: list[dict]) -> str:
    """resultados: {"nombre", "resultado" (ver MARCAS), "victorias", "segundos", "motivo"} por modo."""
    lineas = [_cabecera("Prueba rápida")]
    for r in resultados:
        partes = [f"{MARCAS.get(r['resultado'], '?')} {r['nombre']}"]
        if r["resultado"] in ("ok", "sin_victoria", "fallo", "detenida") and r.get("segundos"):
            v = int(r.get("victorias", 0))
            partes.append(f"{v} victoria{'s' if v != 1 else ''} · {_tiempo(r['segundos'])}")
        if r.get("motivo"):
            partes.append(r["motivo"])
        lineas.append(" · ".join(partes))
    bien = sum(1 for r in resultados if r["resultado"] == "ok")
    total = sum(r.get("segundos", 0) for r in resultados)
    lineas.append(f"Resultado: {bien} de {len(resultados)} bien · {_tiempo(total)}")
    return "\n".join(lineas)

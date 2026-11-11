"""Escritura atomica de datos locales: el archivo anterior dura hasta el reemplazo.

El temporal se crea junto al destino (mismo volumen), se vacia a disco y se
reemplaza con os.replace. Conserva una copia .bak de la ultima version completa.
Los locks de cada modulo siguen siendo necesarios para operaciones leer-modificar-guardar.
"""

import os
import tempfile
from pathlib import Path


def _reemplazar(ruta: Path, datos: bytes) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    descriptor, nombre = tempfile.mkstemp(
        prefix=f".{ruta.name}.", suffix=".tmp", dir=ruta.parent
    )
    temporal = Path(nombre)
    try:
        with os.fdopen(descriptor, "wb") as archivo:
            archivo.write(datos)
            archivo.flush()
            os.fsync(archivo.fileno())
        os.replace(temporal, ruta)
    finally:
        temporal.unlink(missing_ok=True)


def escribir_texto(ruta: Path, texto: str, *, respaldo: bool = True) -> None:
    """Publica el texto completo o conserva el anterior si falla antes del reemplazo.

    .bak no se carga automaticamente: puede ser mas antiguo que un diario al que
    se han agregado registros. La recuperacion debe ser explicita para no perderlos.
    """
    ruta = Path(ruta)
    datos = texto.encode("utf-8")
    if respaldo and ruta.is_file():
        _reemplazar(ruta.with_name(ruta.name + ".bak"), ruta.read_bytes())
    _reemplazar(ruta, datos)

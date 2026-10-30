"""Publica solos los equipos del administrador (personajes/equipos.yaml) en la base de todos (lumen/datos/equipos.yaml).

Se hace en una copia aparte de la rama remota (git worktree en logs/): la carpeta del programa no se toca y la
actualizacion normal trae el cambio despues. Usa las credenciales de git que ya tiene este PC (el administrador
publica desde aqui); el bot no escribe ninguna contraseña. Si no hay permiso o internet, no pasa nada: se
reintenta la proxima vez.
"""

import shutil
from pathlib import Path

import yaml

from lumen.actualizador import RAMA, ErrorActualizacion, _git
from lumen.rutas import LOGS

BASE_EN_REPO = Path("lumen") / "datos" / "equipos.yaml"
COPIA = LOGS / "publicar_equipos"
INTENTOS = 2  # si alguien publico a la vez, se vuelve a bajar la rama y se reintenta


def pendientes(base: dict, propios: dict) -> dict[str, list[dict]]:
    """Los equipos del admin que aun no estan en la base (mismos personajes = ya publicado)."""
    faltan = {}
    for clave, lista in (propios or {}).items():
        en_base = {frozenset(d.get("personajes") or []) for d in (base or {}).get(clave) or [] if isinstance(d, dict)}
        for datos in lista or []:
            ids = frozenset(datos.get("personajes") or [])
            if ids and ids not in en_base:
                en_base.add(ids)
                faltan.setdefault(clave, []).append(datos)
    return faltan


def _bloque(datos: dict) -> str:
    """El equipo como en la base: "  - nombre: ...", con los personajes en una linea."""
    campos = {k: v for k, v in datos.items() if not k.startswith("_") and k != "propio"}
    lineas = []
    for k, v in campos.items():
        if isinstance(v, list):
            texto = f"[{', '.join(str(x) for x in v)}]"
        elif k == "notas":
            texto = ">-\n" + "\n".join("      " + l for l in str(v).splitlines())
        else:
            texto = yaml.safe_dump(v, allow_unicode=True, default_style=None).strip().removesuffix("...").strip()
        lineas.append(f"{'  - ' if not lineas else '    '}{k}: {texto}")
    return "\n".join(lineas) + "\n"


def insertar(texto: str, clave: str, datos: dict) -> str:
    """Añade el equipo al final de su contenido, conservando los comentarios del archivo."""
    lineas = texto.splitlines(keepends=True)
    inicio = next((i for i, l in enumerate(lineas) if l.rstrip() == f"{clave}:"), None)
    if inicio is None:
        return texto.rstrip("\n") + f"\n\n{clave}:\n" + _bloque(datos)
    fin = inicio + 1
    # El contenido acaba en la primera linea pegada al margen (otra clave o el comentario que la presenta)
    while fin < len(lineas) and (not lineas[fin].strip() or lineas[fin][0] == " "):
        fin += 1
    while fin > inicio + 1 and not lineas[fin - 1].strip():  # antes de las lineas en blanco del final
        fin -= 1
    return "".join(lineas[:fin]) + "\n" + _bloque(datos) + "".join(lineas[fin:])


def _limpiar() -> None:
    try:
        _git("worktree", "remove", "--force", str(COPIA))
    except ErrorActualizacion:
        pass
    shutil.rmtree(COPIA, ignore_errors=True)
    try:
        _git("worktree", "prune")
    except ErrorActualizacion:
        pass


def publicar(propios: dict) -> int:
    """Sube a la rama remota los equipos que faltan. Devuelve cuantos (0 = no habia ninguno nuevo).
    Lanza ErrorActualizacion si git falla (sin permiso, sin internet...)."""
    for intento in range(INTENTOS):
        _limpiar()
        _git("fetch", "origin", RAMA, timeout=120)
        _git("worktree", "add", "--detach", str(COPIA), f"origin/{RAMA}")
        try:
            archivo = COPIA / BASE_EN_REPO
            texto = archivo.read_text(encoding="utf-8")
            faltan = pendientes(yaml.safe_load(texto) or {}, propios)
            if not faltan:
                return 0
            for clave, lista in faltan.items():
                for datos in lista:
                    texto = insertar(texto, clave, datos)
            if pendientes(yaml.safe_load(texto) or {}, propios):  # el archivo nuevo tiene que leerse bien
                raise ErrorActualizacion("No pude escribir los equipos en la base.")
            archivo.write_text(texto, encoding="utf-8")
            n = sum(len(v) for v in faltan.values())
            nombres = ", ".join(d.get("nombre", "?") for v in faltan.values() for d in v)
            _git("-C", str(COPIA), "add", str(BASE_EN_REPO))
            _git("-C", str(COPIA), "commit", "-m", f"Publish admin teams: {nombres}")
            try:
                _git("-C", str(COPIA), "push", "origin", f"HEAD:{RAMA}", timeout=120)
            except ErrorActualizacion:
                if intento + 1 < INTENTOS:
                    continue  # alguien subio algo mientras tanto: otra vuelta sobre la rama nueva
                raise
            return n
        finally:
            _limpiar()
    return 0

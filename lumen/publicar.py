"""Publica solo lo que el administrador agrega, para que les llegue a todos con la actualizacion:

- Equipos (personajes/equipos.yaml) -> lumen/datos/equipos.yaml.
- Heroes nuevos ("Pasar a Personajes" en Heroes: personajes/usuario.yaml) -> lumen/datos/personajes.yaml, con sus
  imagenes (icono y cartas) en assets/personajes/<id>/.
- Retratos de artwork (cara_artwork.jpg y artwork.jpg) de cualquier heroe -> assets/personajes/<id>/.

Se hace en una copia aparte de la rama remota (git worktree en logs/): la carpeta del programa no se toca y la
actualizacion normal trae el cambio despues. Usa las credenciales de git que ya tiene este PC (el administrador
publica desde aqui); el bot no escribe ninguna contraseña. Si no hay permiso o internet, no pasa nada: se
reintenta la proxima vez.
"""

import shutil
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from lumen import personajes as P
from lumen.actualizador import RAMA, ErrorActualizacion, _git
from lumen.rutas import LOGS

EQUIPOS_EN_REPO = Path("lumen") / "datos" / "equipos.yaml"
HEROES_EN_REPO = Path("lumen") / "datos" / "personajes.yaml"
IMAGENES_EN_REPO = Path("assets") / "personajes"
COPIA = LOGS / "publicar"
INTENTOS = 2  # si alguien publico a la vez, se vuelve a bajar la rama y se reintenta
CAMPOS_HEROE = ("clave", "nombre", "color", "raza", "roles", "cartas")
RETRATOS = (P.CARA_ARTWORK, P.ARTWORK)  # se publican de todos los heroes (y se actualizan si cambian)


@dataclass
class Local:
    """Lo que hay en este PC para publicar."""
    equipos: dict = field(default_factory=dict)  # contenido -> [equipo]
    heroes: dict = field(default_factory=dict)  # id -> registro de usuario.yaml (con nombre)
    carpeta: Path = P.CARPETA  # personajes/<id>/ con sus imagenes
    claves: dict = field(default_factory=dict)  # id -> "[titulo] nombre" (de la captura de heroes)

    def vacio(self) -> bool:
        return not self.equipos and not self.heroes and not any(self.carpeta.glob(f"*/{P.CARA_ARTWORK}"))


@dataclass
class Resultado:
    equipos: int = 0
    heroes: int = 0
    retratos: int = 0

    def __bool__(self):
        return bool(self.equipos or self.heroes or self.retratos)

    def texto(self) -> str:
        partes = [f"{n} {nombre}" for n, nombre in ((self.equipos, "equipos"), (self.heroes, "héroes nuevos"),
                                                     (self.retratos, "retratos")) if n]
        return ", ".join(partes)


# ------------------------------------------------------------------ equipos
def equipos_pendientes(base: dict, propios: dict) -> dict[str, list[dict]]:
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


# ------------------------------------------------------------------ heroes
def heroes_pendientes(base: dict, heroes: dict) -> list[str]:
    """Heroes agregados en este PC (con ficha: nombre) que la base aun no tiene."""
    return [pid for pid, d in (heroes or {}).items() if pid not in (base or {}) and (d or {}).get("nombre")]


def registro_heroe(datos: dict, clave: str = "") -> dict:
    r = {"clave": clave, **{k: v for k, v in datos.items() if k in CAMPOS_HEROE}}
    return {k: r[k] for k in CAMPOS_HEROE if r.get(k)}


def _copiar_si_cambia(origen: Path, destino: Path) -> bool:
    if not origen.is_file() or (destino.is_file() and destino.read_bytes() == origen.read_bytes()):
        return False
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(origen, destino)
    return True


def preparar(copia: Path, local: Local) -> Resultado:
    """Escribe en la copia de la rama todo lo que falta publicar. Devuelve que se agrego."""
    hecho = Resultado()
    # Equipos
    archivo = copia / EQUIPOS_EN_REPO
    texto = archivo.read_text(encoding="utf-8")
    faltan = equipos_pendientes(yaml.safe_load(texto) or {}, local.equipos)
    for clave, lista in faltan.items():
        for datos in lista:
            texto = insertar(texto, clave, datos)
    if faltan:
        if equipos_pendientes(yaml.safe_load(texto) or {}, local.equipos):  # tiene que leerse bien
            raise ErrorActualizacion("No pude escribir los equipos en la base.")
        archivo.write_text(texto, encoding="utf-8")
        hecho.equipos = sum(len(v) for v in faltan.values())
    # Heroes nuevos, con su icono y sus cartas
    archivo = copia / HEROES_EN_REPO
    texto = archivo.read_text(encoding="utf-8")
    nuevos = heroes_pendientes(yaml.safe_load(texto) or {}, local.heroes)
    for pid in nuevos:
        bloque = yaml.safe_dump({pid: registro_heroe(local.heroes[pid], local.claves.get(pid, ""))},
                                allow_unicode=True, sort_keys=False, width=110)
        texto = texto.rstrip("\n") + "\n\n" + bloque
        for imagen in sorted((local.carpeta / pid).glob("*.png")):
            if not imagen.stem.endswith("_anterior"):
                _copiar_si_cambia(imagen, copia / IMAGENES_EN_REPO / pid / imagen.name)
    if nuevos:
        if heroes_pendientes(yaml.safe_load(texto) or {}, local.heroes):
            raise ErrorActualizacion("No pude escribir los héroes en la base.")
        archivo.write_text(texto, encoding="utf-8")
        hecho.heroes = len(nuevos)
    # Retratos de artwork de todos los heroes de la base
    base = yaml.safe_load(texto) or {}
    for pid in base:
        cambio = False
        for nombre in RETRATOS:
            cambio |= _copiar_si_cambia(local.carpeta / pid / nombre, copia / IMAGENES_EN_REPO / pid / nombre)
        hecho.retratos += cambio
    return hecho


# ------------------------------------------------------------------ git
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


def publicar(local: Local) -> Resultado:
    """Sube a la rama remota lo que falta. Lanza ErrorActualizacion si git falla (sin permiso, sin internet...)."""
    for intento in range(INTENTOS):
        _limpiar()
        _git("fetch", "origin", RAMA, timeout=120)
        _git("worktree", "add", "--detach", str(COPIA), f"origin/{RAMA}")
        try:
            hecho = preparar(COPIA, local)
            if not hecho:
                return hecho
            _git("-C", str(COPIA), "add", "-A", str(EQUIPOS_EN_REPO), str(HEROES_EN_REPO), str(IMAGENES_EN_REPO))
            _git("-C", str(COPIA), "commit", "-m", f"Publish from Lumen: {hecho.texto()}")
            try:
                _git("-C", str(COPIA), "push", "origin", f"HEAD:{RAMA}", timeout=300)
            except ErrorActualizacion:
                if intento + 1 < INTENTOS:
                    continue  # alguien subio algo mientras tanto: otra vuelta sobre la rama nueva
                raise
            return hecho
        finally:
            _limpiar()
    return Resultado()


def leer_local() -> Local:
    """Lo de este PC: equipos del admin, heroes de usuario.yaml y las claves de la captura de heroes."""
    from lumen.gui.paginas.equipos import PROPIOS, _leer
    from lumen.modos.captura_heroes import cargar_catalogo

    return Local(equipos=_leer(PROPIOS), heroes=P._leer_yaml(P.USUARIO), carpeta=P.CARPETA,
                 claves={pid: h.get("clave", "") for pid, h in cargar_catalogo().items()})

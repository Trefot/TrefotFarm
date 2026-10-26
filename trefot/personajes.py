"""Biblioteca de personajes: ficha de cada personaje y sus capturas, compartidas por todos los modos.

- Catalogo base: trefot/datos/personajes.yaml (lo traen las actualizaciones).
- Lo tuyo: personajes/usuario.yaml (fichas nuevas, cambios, "lo tengo") y personajes/<id>/*.png
  (capturas de cartas y del retrato). Nada de eso esta en git, asi que las actualizaciones no lo tocan.

Una carta se nombra "personaje.carta", p. ej. "odin.single" o "thonar_azul.postura".
"""

import re
import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from trefot.rutas import EQUIPO, IMAGENES, RAIZ
from trefot.vision import Plantilla

BASE = Path(__file__).resolve().parent / "datos" / "personajes.yaml"
CARPETA = RAIZ / "personajes"
USUARIO = CARPETA / "usuario.yaml"

COLORES = ["rojo", "verde", "azul", "claro", "oscuro"]
RAZAS = ["sin definir", "humano", "gigante", "hada", "diosa", "demonio", "desconocida"]
ROLES = {
    "quita_postura": "Quita posturas",
    "dano_single": "Dano a un objetivo",
    "dano_area": "Dano en area",
    "ulti_remate": "Ulti que remata",
    "talento": "Talento util",
    "buff": "Mejora al equipo",
    "debuff": "Debilita enemigos",
    "curacion": "Curacion",
    "aguante": "Aguanta / protege",
}
RETRATO = "retrato"  # captura de la cara en la pantalla del equipo (no es una carta)

_lock = threading.RLock()


@dataclass
class CartaPj:
    id: str
    descripcion: str
    respaldo: str = ""  # imagen de AutoFarming si no hay captura propia
    boton: bool = False  # True = boton de pantalla, no carta de la mano


@dataclass
class Personaje:
    id: str
    nombre: str
    color: str = "rojo"
    raza: str = "sin definir"
    roles: list[str] = field(default_factory=list)
    cartas: dict[str, CartaPj] = field(default_factory=dict)
    tengo: bool = False
    propio: bool = False  # creado por el usuario (no viene en el catalogo base)

    @property
    def carpeta(self) -> Path:
        return CARPETA / self.id

    def ruta(self, carta: str) -> Path:
        return self.carpeta / f"{carta}.png"

    def tiene_captura(self, carta: str) -> bool:
        return self.ruta(carta).is_file()

    def plantilla(self, carta: str) -> Plantilla | None:
        """Captura propia; si no hay, la imagen de respaldo de AutoFarming; si tampoco, None."""
        rutas = [self.ruta(carta)] if self.tiene_captura(carta) else []
        c = self.cartas.get(carta)
        if c and c.respaldo and (IMAGENES / c.respaldo).is_file():
            rutas.append(IMAGENES / c.respaldo)
        return Plantilla(*rutas, nombre=f"{self.id}.{carta}") if rutas else None

    def estado_carta(self, carta: str) -> str:
        if self.tiene_captura(carta):
            return "propia"
        c = self.cartas.get(carta)
        if c and c.respaldo and (IMAGENES / c.respaldo).is_file():
            return "respaldo"
        return "falta"


# ------------------------------------------------------------------ carga / guardado
def _leer_yaml(ruta: Path) -> dict:
    if not ruta.is_file():
        return {}
    with ruta.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _crear(pid: str, datos: dict, propio: bool) -> Personaje:
    cartas = {}
    for cid, c in (datos.get("cartas") or {}).items():
        c = c or {}
        cartas[cid] = CartaPj(cid, c.get("descripcion", cid), c.get("respaldo", ""), bool(c.get("boton", False)))
    return Personaje(
        id=pid,
        nombre=datos.get("nombre", pid),
        color=datos.get("color", "rojo"),
        raza=datos.get("raza", "sin definir"),
        roles=list(datos.get("roles") or []),
        cartas=cartas,
        tengo=bool(datos.get("tengo", False)),
        propio=propio,
    )


def _primera_vez():
    """Al estrenar la biblioteca: marca como tuyos los personajes del equipo de Perros y mueve
    las capturas que hubiera de la version anterior (assets/equipo/perros_trefot)."""
    CARPETA.mkdir(parents=True, exist_ok=True)
    if not USUARIO.is_file():
        datos = {pid: {"tengo": True} for pid in ("odin", "gawain", "freyja_roja", "thonar_azul")}
        USUARIO.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")
    viejo = EQUIPO / "perros_trefot"
    nombres_viejos = {
        "odin_single": ("odin", "single"), "odin_area": ("odin", "area"), "odin_ulti": ("odin", "ulti"),
        "odin_talento": ("odin", "talento"), "gawain_single": ("gawain", "single"), "gawain_area": ("gawain", "area"),
        "gawain_ulti": ("gawain", "ulti"), "freyja_1": ("freyja_roja", "normal_1"), "freyja_2": ("freyja_roja", "normal_2"),
        "freyja_ulti": ("freyja_roja", "ulti"), "thonar_postura": ("thonar_azul", "postura"),
        "thonar_otra": ("thonar_azul", "otra"), "thonar_ulti": ("thonar_azul", "ulti"),
    }
    if viejo.is_dir():
        for archivo in viejo.glob("*.png"):
            destino = nombres_viejos.get(archivo.stem)
            if destino:
                ruta = CARPETA / destino[0] / f"{destino[1]}.png"
                if not ruta.exists():
                    ruta.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(archivo), ruta)


def cargar() -> dict[str, Personaje]:
    with _lock:
        _primera_vez()
        base = _leer_yaml(BASE)
        usuario = _leer_yaml(USUARIO)
        resultado = {}
        for pid in list(base) + [p for p in usuario if p not in base]:
            datos = dict(base.get(pid) or {})
            cambios = usuario.get(pid) or {}
            cartas = dict(datos.get("cartas") or {})
            cartas.update(cambios.get("cartas") or {})
            datos.update({k: v for k, v in cambios.items() if k != "cartas"})
            datos["cartas"] = cartas
            resultado[pid] = _crear(pid, datos, propio=pid not in base)
        return resultado


def guardar(p: Personaje) -> None:
    """Guarda la ficha en personajes/usuario.yaml (solo lo que difiere del catalogo base)."""
    with _lock:
        usuario = _leer_yaml(USUARIO)
        base = (_leer_yaml(BASE).get(p.id) or {})
        registro = {"nombre": p.nombre, "color": p.color, "raza": p.raza, "roles": list(p.roles), "tengo": p.tengo}
        cartas_base = base.get("cartas") or {}
        extra = {
            c.id: {"descripcion": c.descripcion, **({"boton": True} if c.boton else {})}
            for c in p.cartas.values()
            if c.id not in cartas_base
        }
        if extra:
            registro["cartas"] = extra
        usuario[p.id] = registro
        CARPETA.mkdir(parents=True, exist_ok=True)
        USUARIO.write_text(yaml.safe_dump(usuario, allow_unicode=True, sort_keys=False), encoding="utf-8")


def borrar_propio(pid: str) -> None:
    """Quita de la biblioteca un personaje creado por el usuario (sus capturas se conservan en disco)."""
    with _lock:
        usuario = _leer_yaml(USUARIO)
        if pid in usuario and pid not in _leer_yaml(BASE):
            del usuario[pid]
            USUARIO.write_text(yaml.safe_dump(usuario, allow_unicode=True, sort_keys=False), encoding="utf-8")


def nuevo_id(nombre: str, existentes) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", nombre.lower().strip()).strip("_") or "personaje"
    pid, n = base, 2
    while pid in existentes:
        pid, n = f"{base}_{n}", n + 1
    return pid


def separar(clave: str) -> tuple[str, str]:
    """'odin.single' -> ('odin', 'single')."""
    pid, _, carta = clave.partition(".")
    return pid, carta

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
from trefot.vision import Plantilla, guardar_imagen

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

# Cartas sacadas de la ficha del heroe (Heroes -> personaje -> fila "Skills"). Medido con capturas
# reales: la carta de la ficha es mas pequena que en la mano (x1.22 de ancho, x1.26 de alto) y,
# reescalada, reconoce la carta en pelea con 0.60-0.81 frente a <=0.39 de las demas cartas.
SUFIJO_FICHA = "_ficha"
ESCALA_FICHA = (1.22, 1.26)
UMBRAL_PROPIA = 0.7
UMBRAL_FICHA = 0.55

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

    def ruta_ficha(self, carta: str) -> Path:
        """Carta sacada de la ficha del heroe (ya reescalada al tamano de la mano)."""
        return self.carpeta / f"{carta}{SUFIJO_FICHA}.png"

    def tiene_captura(self, carta: str) -> bool:
        return self.ruta(carta).is_file()

    def _respaldo(self, carta: str) -> Path | None:
        c = self.cartas.get(carta)
        ruta = IMAGENES / c.respaldo if c and c.respaldo else None
        return ruta if ruta and ruta.is_file() else None

    def estado_carta(self, carta: str) -> str:
        """'propia' (de una pelea) > 'ficha' (de la ficha del heroe) > 'respaldo' (AutoFarming) > 'falta'."""
        if self.tiene_captura(carta):
            return "propia"
        if self.ruta_ficha(carta).is_file():
            return "ficha"
        if self._respaldo(carta):
            return "respaldo"
        return "falta"

    def plantilla(self, carta: str) -> tuple[Plantilla | None, float]:
        """La mejor imagen disponible para reconocer la carta y el umbral con que se compara."""
        estado = self.estado_carta(carta)
        nombre = f"{self.id}.{carta}"
        if estado == "propia":
            return Plantilla(self.ruta(carta), nombre=nombre), UMBRAL_PROPIA
        if estado == "ficha":
            return Plantilla(self.ruta_ficha(carta), nombre=nombre), UMBRAL_FICHA
        if estado == "respaldo":
            return Plantilla(self._respaldo(carta), nombre=nombre), UMBRAL_PROPIA
        return None, UMBRAL_PROPIA


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


def ruta_anterior(ruta: Path) -> Path:
    return ruta.with_name(f"{ruta.stem}_anterior{ruta.suffix}")


def guardar_con_respaldo(ruta: Path, imagen) -> None:
    """Guarda una captura; si ya habia una, la deja como <nombre>_anterior.png para poder deshacer."""
    if ruta.is_file():
        shutil.copy2(ruta, ruta_anterior(ruta))
    guardar_imagen(ruta, imagen)


def volver_a_anterior(ruta: Path) -> bool:
    """Intercambia la captura actual con la anterior (deshacer / rehacer)."""
    anterior = ruta_anterior(ruta)
    if not anterior.is_file():
        return False
    temporal = ruta.with_name(f"{ruta.stem}_tmp{ruta.suffix}")
    if ruta.is_file():
        ruta.replace(temporal)
    anterior.replace(ruta)
    if temporal.is_file():
        temporal.replace(anterior)
    return True


def separar(clave: str) -> tuple[str, str]:
    """'odin.single' -> ('odin', 'single')."""
    pid, _, carta = clave.partition(".")
    return pid, carta

"""Catalogo de todo lo que el bot va a farmear, este hecho o no.

Cada contenido es una parada de la rueda de Inicio (una bestia, un demonio...) con sus destinos
(los pisos de la bestia; o uno solo). Cada destino tiene un id fijo: cuando su modo esta
programado, ese id coincide con el de su clase en MODOS y se puede farmear; si no, sale como
"Próximamente".

Para programar uno: copia modos/perros_piso4.py, usa el mismo id que aqui y anadelo a MODOS.
Para cambiar la foto de un contenido: pon assets/modos/<id del contenido>.png.
"""

from dataclasses import dataclass, field

from lumen.rutas import ASSETS, IMAGENES

CARPETA_FOTOS = ASSETS / "modos"


@dataclass(frozen=True)
class Destino:
    id: str
    nombre: str  # "Floor 4"; vacio si el contenido tiene un solo destino


@dataclass(frozen=True)
class Contenido:
    id: str
    nombre: str  # tal como sale en el juego
    descripcion: str  # una linea corta
    icono: str  # icono si no hay foto (Material Design Icons)
    imagen: str = ""  # foto por defecto, relativa a assets/imagenes
    destinos: tuple[Destino, ...] = field(default=())

    @property
    def foto(self):
        propia = CARPETA_FOTOS / f"{self.id}.png"
        if propia.is_file():
            return propia
        return IMAGENES / self.imagen if self.imagen else None


def _bestia(id_base: str, nombre: str, imagen: str) -> Contenido:
    pisos = tuple(Destino(f"{id_base}_piso{n}", f"Floor {n}") for n in range(1, 5))
    return Contenido(id_base, nombre, "Bestia demoníaca", "mdi6.paw", imagen, pisos)


def _unico(id_: str, nombre: str, descripcion: str, icono: str) -> Contenido:
    return Contenido(id_, nombre, descripcion, icono, destinos=(Destino(id_, ""),))


CATALOGO: list[Contenido] = [
    _bestia("perros", "Skollandhati & Hati", "demonic_beasts/skollandhati.png"),
    _bestia("pajaro", "Hraesvelgr", "demonic_beasts/hraesvelgr.png"),
    _bestia("ciervo", "Eikthyrnir", "deer/Eikthyrnir.png"),
    _bestia("serpiente", "Nidhoggr", "snake/nidhoggr.png"),
    _bestia("rata", "Ratatoskr", "rat/ratatoskr.png"),
    _unico("demonio_rojo", "Red Demon", "Demonio", "mdi6.fire"),
    _unico("demonio_gris", "Gray Demon", "Demonio", "mdi6.weather-fog"),
    _unico("demonio_carmesi", "Crimson Demon", "Demonio", "mdi6.water"),
    _unico("bellmoth", "Bellmoth", "Demonio", "mdi6.butterfly-outline"),
    _unico("indura", "Indura", "Demonio", "mdi6.skull-crossbones-outline"),
    _unico("oro", "Oro", "Farmeo de oro", "mdi6.gold"),
    _unico("monedas_sa", "Monedas SA", "Farmeo de monedas", "mdi6.circle-multiple-outline"),
]


def contenido_de(id_destino: str) -> Contenido | None:
    for c in CATALOGO:
        if any(d.id == id_destino for d in c.destinos):
            return c
    return None

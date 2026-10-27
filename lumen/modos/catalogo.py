"""Catalogo de todo lo que el bot va a farmear, este hecho o no.

Cada contenido tiene un id fijo. Cuando su modo esta programado, el id coincide con el de su clase
en MODOS y aparece como "Listo"; si no, sale como "Próximamente" en Inicio.

Para programar uno: copia modos/perros_piso4.py, usa el mismo id que aqui y anadelo a MODOS.
"""

from dataclasses import dataclass

CATEGORIAS = {
    "bestias": "Demonic Beasts",
    "demonios": "Demonios",
    "recursos": "Oro y monedas",
}


@dataclass(frozen=True)
class Contenido:
    id: str
    categoria: str  # clave de CATEGORIAS
    grupo: str  # lo que agrupa en una fila (la bestia, el demonio...)
    nombre: str  # nombre tal como sale en el juego
    imagen: str = ""  # emblema, relativo a assets/imagenes


def _bestia(id_base: str, nombre: str, imagen: str = "") -> list[Contenido]:
    return [Contenido(f"{id_base}_piso{n}", "bestias", nombre, f"Floor {n}", imagen) for n in range(1, 5)]


CATALOGO: list[Contenido] = [
    *_bestia("pajaro", "Hraesvelgr", "demonic_beasts/hraesvelgr.png"),
    *_bestia("ciervo", "Eikthyrnir"),
    *_bestia("perros", "Skollandhati & Hati", "demonic_beasts/skollandhati.png"),
    *_bestia("serpiente", "Nidhoggr"),
    *_bestia("rata", "Ratatoskr"),
    Contenido("demonio_rojo", "demonios", "Demonios", "Red Demon"),
    Contenido("demonio_gris", "demonios", "Demonios", "Gray Demon"),
    Contenido("demonio_carmesi", "demonios", "Demonios", "Crimson Demon"),
    Contenido("bellmoth", "demonios", "Demonios", "Bellmoth"),
    Contenido("indura", "demonios", "Demonios", "Indura"),
    Contenido("oro", "recursos", "Recursos", "Farmeo de oro"),
    Contenido("monedas_sa", "recursos", "Recursos", "Monedas SA"),
]


def por_grupo() -> dict[str, dict[str, list[Contenido]]]:
    """{categoria: {grupo: [contenidos]}} en el orden del catalogo."""
    salida: dict[str, dict[str, list[Contenido]]] = {c: {} for c in CATEGORIAS}
    for c in CATALOGO:
        salida[c.categoria].setdefault(c.grupo, []).append(c)
    return salida

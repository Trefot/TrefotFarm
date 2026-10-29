"""Lo que se puede conseguir en cada contenido (lumen/datos/premios.yaml), para mostrarlo en Inicio."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from lumen.rutas import ASSETS

ARCHIVO = Path(__file__).resolve().parent / "datos" / "premios.yaml"
ICONOS = ASSETS / "premios"


@dataclass
class Premio:
    """Un objeto con todas sus lineas de la tabla juntas: cantidades posibles y probabilidad total."""

    objeto: str
    nombre: str
    descripcion: str
    cantidades: list[int]
    prob: float  # % por pelea (suma de sus lineas)
    cajas: list[str]
    siempre: bool = False  # garantizado: sale en cada victoria

    @property
    def icono(self) -> Path:
        return ICONOS / f"{self.objeto}.png"

    @property
    def texto_cantidad(self) -> str:
        """"" (x1), "×5" o "×2–5"."""
        cs = sorted(set(self.cantidades))
        if cs == [1]:
            return ""
        return f"×{cs[0]}" if len(cs) == 1 else f"×{cs[0]}–{cs[-1]}"

    @property
    def texto_prob(self) -> str:
        if self.siempre:
            return "Siempre"
        return f"{self.prob:.1f}".rstrip("0").rstrip(".").replace(".", ",") + " %"


@lru_cache(maxsize=1)
def _datos() -> dict:
    if not ARCHIVO.is_file():
        return {}
    with ARCHIVO.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def de(id_destino: str) -> list[Premio]:
    """Los premios de un destino, en el orden de la tabla del juego, cada objeto una vez."""
    datos = _datos()
    objetos = datos.get("objetos") or {}
    juntos: dict[str, Premio] = {}
    destino = datos.get(id_destino) or {}
    for linea in destino.get("garantizados") or []:  # primero lo seguro
        oid = linea["objeto"]
        info = objetos.get(oid) or {}
        juntos[f"{oid}@siempre"] = Premio(oid, info.get("nombre", oid), info.get("descripcion", ""),
                                          [int(linea.get("cantidad", 1))], 100.0, [], siempre=True)
    for linea in destino.get("premios") or []:
        oid = linea["objeto"]
        info = objetos.get(oid) or {}
        p = juntos.setdefault(oid, Premio(oid, info.get("nombre", oid), info.get("descripcion", ""), [], 0.0, []))
        p.cantidades.append(int(linea.get("cantidad", 1)))
        p.prob += float(linea.get("prob", 0))
        if linea.get("caja") and linea["caja"] not in p.cajas:
            p.cajas.append(linea["caja"])
    return list(juntos.values())


def info(objeto: str) -> dict:
    """nombre, descripcion y galeria (id en la galeria del inventario, si esta) de un objeto de las tablas."""
    return dict((_datos().get("objetos") or {}).get(objeto) or {})


def objetos_de(id_destino: str) -> set[str]:
    """Todo lo que puede salir en un destino: primera vez, garantizados, lider y la tabla."""
    destino = _datos().get(id_destino) or {}
    return {linea["objeto"] for parte in ("primera_vez", "garantizados", "lider", "premios")
            for linea in destino.get(parte) or []}


def donde_sale(objeto: str) -> list[str]:
    """Ids de los destinos en cuya tabla sale el objeto, en el orden del archivo."""
    return [d for d in _datos() if d != "objetos" and objeto in objetos_de(d)]


def todos() -> list[str]:
    """Ids de todos los objetos de las tablas."""
    return list(_datos().get("objetos") or {})


def esperado(id_destino: str, objeto: str) -> float:
    """Cuantos da de media cada victoria: lo garantizado mas cada linea de la tabla por su probabilidad."""
    destino = _datos().get(id_destino) or {}
    total = sum(int(l.get("cantidad", 1)) for l in destino.get("garantizados") or [] if l["objeto"] == objeto)
    return total + sum(float(l.get("prob", 0)) / 100 * int(l.get("cantidad", 1))
                       for l in destino.get("premios") or [] if l["objeto"] == objeto)

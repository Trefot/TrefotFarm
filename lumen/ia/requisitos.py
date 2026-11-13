"""Lo que pide cada jefe por fase (lumen/datos/requisitos_bestias.yaml) y los modos de juego que salen de ahi.

- ``de(destino, fase)``: los requisitos de esa fase ([{tipo, obligatorio, ...}]).
- ``Estilo``: cauteloso (cumple todo), whale (maximo dano y solo lo obligatorio) o automatico (empieza en whale y,
  si una fase no cae en 1 turno, la juega en cauteloso; lo recuerda para las siguientes peleas de la sesion).
"""

from functools import lru_cache
from pathlib import Path

import yaml

ARCHIVO = Path(__file__).resolve().parents[1] / "datos" / "requisitos_bestias.yaml"
CAUTELOSO, WHALE, AUTOMATICO = "Cauteloso", "Whale", "Automático"
ESTILOS = [AUTOMATICO, CAUTELOSO, WHALE]


@lru_cache(maxsize=1)
def _datos() -> dict:
    try:
        return yaml.safe_load(ARCHIVO.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}


def de(destino: str, fase: int | None) -> list[dict]:
    fases = _datos().get(destino) or {}
    return list(fases.get(fase) or fases.get(str(fase)) or [])


def pide(destino: str, fase: int | None, tipo: str) -> dict | None:
    return next((r for r in de(destino, fase) if r.get("tipo") == tipo), None)


def saltable(destino: str, fase: int | None) -> bool:
    """La fase solo tiene requisitos que se saltan con dano (o ninguno)."""
    return not any(r.get("obligatorio") for r in de(destino, fase))


def aplica(requisito: dict | None, turno: int) -> bool:
    """Si el requisito cuenta en este turno de la fase (``turnos: impares`` / ``pares``)."""
    if not requisito:
        return False
    cuando = requisito.get("turnos")
    if cuando == "impares":
        return turno % 2 == 1
    if cuando == "pares":
        return turno % 2 == 0
    return True


class Estilo:
    """Decide, fase a fase, si se juega con cautela o con todo."""

    def __init__(self, nombre: str = AUTOMATICO):
        self.nombre = nombre if nombre in ESTILOS else AUTOMATICO
        self.fases_lentas: set[int] = set()  # fases que no cayeron en 1 turno con todo (modo automatico)

    def whale(self, destino: str, fase: int | None, turno: int) -> bool:
        """True: maximo dano en este turno (lo obligatorio se cumple igual)."""
        if self.nombre == CAUTELOSO:
            return False
        if self.nombre == WHALE:
            return True
        if not saltable(destino, fase):  # en automatico, las fases con algo obligatorio, con cautela
            return False
        if turno > 1 and fase is not None:
            self.fases_lentas.add(fase)  # con todo no cayo en 1 turno: desde ahora, con cautela
        return fase not in self.fases_lentas

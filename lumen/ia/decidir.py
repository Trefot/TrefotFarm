"""Decidir (pieza 4 de IA.md): el valor de cada carta segun lo que pide el jefe ahora.

El juego inteligente (lumen/inteligencia.py) ya puntua cada jugada con un valor por carta. Aqui ese valor
se multiplica por lo que piden las mecanicas de la fase (lumen/datos/jefes.yaml, leidas por
lumen/ia/efectos.py) y por lo que hace cada carta (su texto, de la captura de heroes):

- Postura: las cartas que la quitan valen x3.
- Mecanica que se vence con la ulti (Torrent, la curacion del ciervo): las ultis x2.
- Evasion: las que la ignoran x3, las ultis x1.5 y el resto del dano x0.6 (no malgastarlo).
- Bloqueo de habilidades: las que limpian x3.
- "Mismo atributo" (reduccion de dano, proteccion): las del color que ya se esta jugando x1.5, el resto x0.7.
- Inmortalidad que cae con golpes: las cartas de varios golpes x1.5.
- Bonus por orbes llenos (critico del ciervo F3): las ultis x0.6 (mejor tener los orbes llenos).

Cada ajuste deja su motivo (``razones``) para el diario de peleas (pieza 5). Los pesos son el punto de
partida: la pieza 6 (aprender solo) los ajustara con los resultados.
"""

from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

import yaml

from lumen.ia.efectos import Efecto, Mecanica, efectos, jefe

JEFES = Path(__file__).resolve().parents[1] / "datos" / "jefes.yaml"
PESOS = {
    "quita_postura": 3.0,
    "ulti_contra": 2.0,
    "ignora_evasion": 3.0,
    "ulti_evasion": 1.5,
    "dano_con_evasion": 0.6,
    "limpia_bloqueo": 3.0,
    "mismo_color": 1.5,
    "otro_color": 0.7,
    "varios_golpes": 1.5,
    "guardar_orbes": 0.6,
}


def base(nombre: str) -> str:
    """"heroe.carta@2" -> "heroe.carta" (el @ separa grupos de dibujo en inteligencia.py)."""
    return nombre.split("@")[0]


def es_ulti(nombre: str) -> bool:
    return base(nombre).endswith(".ulti")


# ------------------------------------------------------------------ jefes
@lru_cache(maxsize=1)
def _jefes() -> dict:
    if not JEFES.is_file():
        return {}
    return yaml.safe_load(JEFES.read_text(encoding="utf-8")) or {}


def mecanicas_de(id_destino: str, fase: int) -> list[Mecanica]:
    """Las mecanicas de una fase de un jefe (las de sus textos de Enemy Info)."""
    textos = ((_jefes().get(id_destino) or {}).get("fases") or {}).get(fase) or []
    return jefe(textos)


# ------------------------------------------------------------------ cartas
class LectorCartas:
    """Los efectos y el color de cada carta "heroe.carta", con los textos de la captura de heroes."""

    def __init__(self, biblioteca: dict | None = None, textos: dict[str, str] | None = None):
        from lumen import personajes as P

        self.biblioteca = P.cargar() if biblioteca is None else biblioteca
        self.textos = textos_por_habilidad() if textos is None else textos
        self._cache: dict[str, list[Efecto]] = {}

    def efectos_de(self, nombre: str) -> list[Efecto]:
        clave = base(nombre)
        if clave not in self._cache:
            from lumen.valor_cartas import nombre_de_habilidad

            pid, _, cid = clave.partition(".")
            carta = (self.biblioteca[pid].cartas.get(cid) if pid in self.biblioteca else None)
            texto = self.textos.get(nombre_de_habilidad(carta.descripcion)) if carta else None
            self._cache[clave] = efectos(texto) if texto else []
        return self._cache[clave]

    def color_de(self, nombre: str) -> str | None:
        pj = self.biblioteca.get(base(nombre).partition(".")[0])
        return pj.color if pj else None


def textos_por_habilidad() -> dict[str, str]:
    """nombre de la habilidad (en minusculas) -> su texto, de la captura de heroes de esta PC."""
    from lumen.valor_cartas import CATALOGO_TEXTOS

    if not CATALOGO_TEXTOS.is_file():
        return {}
    try:
        catalogo = yaml.safe_load(CATALOGO_TEXTOS.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return {(c.get("nombre") or "").strip().lower(): c["texto"]
            for h in catalogo.values() for c in (h or {}).get("cartas") or [] if c.get("texto") and c.get("nombre")}


# ------------------------------------------------------------------ ajustar
def ajustar(valores: dict[str, float], mecanicas: list[Mecanica], efectos_de: Callable[[str], list[Efecto]],
            color_de: Callable[[str], str | None], color_turno: str | None = None) -> tuple[dict, dict]:
    """(valores ajustados, razones): cada carta multiplicada por lo que piden las mecanicas de la fase."""
    tipos = {m.tipo for m in mecanicas}
    contras = {c for m in mecanicas if m.tipo != "evasion" for c in m.contra}
    nuevos, razones = {}, {}
    for nombre, valor in valores.items():
        efs = efectos_de(nombre) or []
        hace = {e.tipo for e in efs}
        ulti = es_ulti(nombre)
        factor, motivos = 1.0, []

        def aplicar(peso: str, motivo: str):
            nonlocal factor
            factor *= PESOS[peso]
            motivos.append(motivo)

        if "quitar_postura" in contras and "quitar_postura" in hace:
            aplicar("quita_postura", "quita la postura")
        if "ulti" in contras and ulti:
            aplicar("ulti_contra", "la ulti vence una mecánica")
        if "evasion" in tipos:
            if "ignora_evasion" in hace:
                aplicar("ignora_evasion", "ignora la evasión")
            elif ulti:
                aplicar("ulti_evasion", "ulti contra la evasión")
            elif "dano" in hace:
                aplicar("dano_con_evasion", "el jefe esquiva")
        if "limpiar" in contras and "limpiar" in hace:
            aplicar("limpia_bloqueo", "limpia el bloqueo")
        if "mismo_atributo" in contras and color_turno:
            if color_de(nombre) == color_turno:
                aplicar("mismo_color", f"sigue el {color_turno}")
            else:
                aplicar("otro_color", f"rompe el {color_turno}")
        if "golpes" in contras and sum(e.tipo == "dano" for e in efs) >= 2:
            aplicar("varios_golpes", "varios golpes contra la inmortalidad")
        if "cargar_ulti" in contras and ulti:
            aplicar("guardar_orbes", "orbes llenos dan crítico")
        nuevos[nombre] = valor * factor
        if motivos:
            razones[nombre] = motivos
    return nuevos, razones

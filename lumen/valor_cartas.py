"""Cuanto vale cada carta, para que el juego inteligente (lumen/inteligencia.py) elija bien.

Dos fuentes, de menos a mas precisa:
1. El tipo de la carta en la base de personajes (lumen/datos/personajes.yaml): "Un objetivo (Spinning
   Slicer)", "Área (Noxious Blitz)", "Apoyo (...)", "Defensa (...)". Con eso y cuantos enemigos hay en
   la pelea se estima su dano relativo (VALOR_TIPO).
2. El texto completo de la carta, si esta PC hizo la captura de heroes (capturas/heroes/catalogo.yaml,
   no va en git): "Deals damage equal to 200% of Attack to all enemies". De ahi sale el porcentaje real.

Los valores son relativos (1.0 = una carta normal de un objetivo): sirven para comparar jugadas, no para
saber el dano exacto (falta el ataque de cada heroe, la defensa del jefe, etc.).
"""

import re
from pathlib import Path

import yaml

from lumen import personajes as P
from lumen.rutas import RAIZ

CATALOGO_TEXTOS = RAIZ / "capturas" / "heroes" / "catalogo.yaml"
PORCENTAJE_NORMAL = 150.0  # % de ataque de una carta "normal" de un objetivo (para pasar % a valor relativo)
# Dano relativo por tipo con UN enemigo. El de area se multiplica por los enemigos (hasta 3).
VALOR_TIPO = {"single": 1.0, "area": 0.8, "apoyo": 0.5, "defensa": 0.4, "otro": 0.7}
PREFIJOS = {"un objetivo": "single", "área": "area", "area": "area", "apoyo": "apoyo", "defensa": "defensa",
            "quita": "single"}
_PORCENTAJE = re.compile(r"(\d{2,4})\s*%\s*of\s*(?:the\s+)?(?:its\s+|their\s+)?(?:attack|atk)", re.I)


def tipo_de(descripcion: str) -> str:
    """single / area / apoyo / defensa / otro, del texto corto de la base ("Área (Noxious Blitz)")."""
    t = (descripcion or "").strip().lower()
    for prefijo, tipo in PREFIJOS.items():
        if t.startswith(prefijo):
            return tipo
    return "otro"


def nombre_de_habilidad(descripcion: str) -> str:
    """"Área (Noxious Blitz)" -> "noxious blitz" (para cruzarlo con el texto completo)."""
    m = re.search(r"\((.+)\)\s*$", descripcion or "")
    return m.group(1).strip().lower() if m else ""


def porcentaje(texto: str) -> float | None:
    """Suma de los "X% of Attack" del texto de la carta (algunas pegan dos veces), o None si no tiene."""
    valores = [float(v) for v in _PORCENTAJE.findall(texto or "")]
    return sum(valores) if valores else None


def porcentajes_locales(ruta: Path = CATALOGO_TEXTOS) -> dict[str, float]:
    """nombre de habilidad -> % de ataque, del catalogo de la captura de heroes de esta PC (si existe)."""
    if not ruta.is_file():
        return {}
    try:
        with ruta.open(encoding="utf-8") as f:
            catalogo = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {}
    salida = {}
    for heroe in catalogo.values():
        for carta in (heroe or {}).get("cartas") or []:
            pct = porcentaje(carta.get("texto", ""))
            nombre = (carta.get("nombre") or "").strip().lower()
            if pct and nombre:
                salida[nombre] = pct
    return salida


class Tasador:
    """Da el valor de cada carta "heroe.carta" para una pelea con ``enemigos`` enemigos."""

    def __init__(self, enemigos: int = 1, biblioteca: dict | None = None, porcentajes: dict | None = None):
        self.enemigos = max(1, enemigos)
        self.biblioteca = biblioteca if biblioteca is not None else P.cargar()
        self.porcentajes = porcentajes if porcentajes is not None else porcentajes_locales()
        self._cache: dict[str, float] = {}

    def valor(self, nombre: str) -> float:
        if nombre not in self._cache:
            self._cache[nombre] = self._calcular(nombre)
        return self._cache[nombre]

    def _calcular(self, nombre: str) -> float:
        pid, _, cid = nombre.split("@")[0].partition(".")  # "heroe.carta@2": el @ separa grupos de dibujo
        pj = self.biblioteca.get(pid)
        carta = pj.cartas.get(cid) if pj else None
        if carta is None:
            return 1.0  # no se sabe que carta es: una normal
        tipo = tipo_de(carta.descripcion)
        pct = self.porcentajes.get(nombre_de_habilidad(carta.descripcion))
        enemigos = min(self.enemigos, 3)
        if cid == "ulti":  # la ulti ya vale VALOR_ULTI en inteligencia.py: aqui solo cuenta si pega a todos
            return max(1.0, 0.8 * enemigos) if tipo == "area" else 1.0
        base = (pct / PORCENTAJE_NORMAL) if pct else VALOR_TIPO[tipo]
        return base * enemigos if tipo == "area" else base

    def valores(self, nombres) -> dict[str, float]:
        return {n: self.valor(n) for n in nombres if n and "." in n.split("@")[0]}

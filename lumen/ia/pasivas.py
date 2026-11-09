"""Pasivas de los heroes (paso 1 de IA.md): que el juego inteligente sepa cuanto mas vale cada carta por la pasiva
unica de su heroe, y contra que jefe (datos de 7dshub, en lumen/datos/fichas.yaml).

Se leen los patrones que cambian que carta conviene jugar (vistos en las pasivas de los 381 heroes, 2026-11-09):
- "increases the hero's damage dealt by N%"                      -> todas sus cartas valen (1 + N/100)
- "the hero's damage dealt using/with single-target attacks by N%" -> sus cartas de un objetivo
- "... all-target attacks by N%"                                  -> sus cartas de area
- "Ultimate Move damage ... by N%"                                -> su ulti
Y cuando se aplica: "only activates in Demonic Beast Battle Ratatoskr" (solo contra ese jefe), "In Demonic Beast
Battle" (en cualquier bestia) o siempre. P. ej. Jormungand rojo: +200 % con ataques de un objetivo, solo contra
Ratatoskr -> ahi sus cartas de un objetivo valen x3.

Lo que sube a todos los aliados por igual no cambia que carta elegir, asi que no se cuenta. Las reliquias se leen
igual (``leer``) pero no se aplican: el bot no sabe si el jugador la tiene puesta.
"""

import re
from functools import lru_cache

# Destino del bot (p. ej. "rata_f2", "perros_piso4", "indura_chaos") -> nombre del jefe como lo escriben las pasivas
JEFES = {"pajaro": "hraesvelgr", "ciervo": "eikthyrnir", "perros": "skoll and hati", "serpiente": "nidhoggr",
         "rata": "ratatoskr", "surtr": "surtr", "indura": "indura"}
BESTIAS = {"pajaro", "ciervo", "perros", "serpiente", "rata", "surtr"}
MAX_FACTOR = 4.0

_N = r"(\d+(?:\.\d+)?)\s*%"
_PATRONES = (
    ("uno", re.compile(r"hero's damage dealt (?:using|with) single-target attacks? (?:increases? )?by " + _N, re.I)),
    ("area", re.compile(r"hero's damage dealt (?:using|with) all-target attacks? (?:increases? )?by " + _N, re.I)),
    ("ulti", re.compile(r"(?:hero's )?ultimate move damage (?:dealt )?(?:increases? )?by " + _N, re.I)),
    ("todas", re.compile(r"increases? the hero's damage dealt by " + _N, re.I)),
)
_SOLO_JEFE = re.compile(r"only activates in demonic beast battle ([a-z' ]+?)[.,\\]", re.I)
_EN_BESTIAS = re.compile(r"in demonic beast battle", re.I)


def _limpio(texto: str) -> str:
    return re.sub(r"\[[0-9A-Fa-f]{6}\]|\[-\]", "", texto or "").replace("\\n", " ").replace("\n", " ")


def leer(texto: str) -> dict:
    """{"jefe": nombre | None, "bestias": bool, "uno": x, "area": x, "ulti": x, "todas": x} (x = multiplicador)."""
    t = _limpio(texto)
    salida = {"jefe": None, "bestias": False, "uno": 1.0, "area": 1.0, "ulti": 1.0, "todas": 1.0}
    m = _SOLO_JEFE.search(t)
    if m:
        salida["jefe"] = m.group(1).strip().lower()
    elif _EN_BESTIAS.search(t):
        salida["bestias"] = True
    for clave, patron in _PATRONES:
        for valor in patron.findall(t):
            salida[clave] = min(MAX_FACTOR, salida[clave] * (1 + float(valor) / 100))
    return salida


def _jefe_de(destino: str) -> tuple[str, bool]:
    prefijo = (destino or "").split("_")[0]
    return JEFES.get(prefijo, ""), prefijo in BESTIAS


def aplica(pasiva: dict, destino: str) -> bool:
    jefe, es_bestia = _jefe_de(destino)
    if pasiva["jefe"]:
        return bool(jefe) and pasiva["jefe"].startswith(jefe.split()[0])
    if pasiva["bestias"]:
        return es_bestia
    return True


@lru_cache(maxsize=512)
def pasiva_de(pid: str) -> dict:
    from lumen import personajes as P

    return leer(((P.ficha(pid) or {}).get("pasiva") or {}).get("texto", ""))


def factor(nombre: str, destino: str, es_area=None) -> float:
    """Cuanto mas vale esta carta ("heroe.carta") por la pasiva de su heroe en este destino."""
    base = (nombre or "").split("@")[0]
    if "." not in base:
        return 1.0
    pid, _, cid = base.partition(".")
    pasiva = pasiva_de(pid)
    if not aplica(pasiva, destino):
        return 1.0
    f = pasiva["todas"]
    if cid == "ulti":
        return min(MAX_FACTOR, f * pasiva["ulti"])
    area = False
    if es_area is not None:
        try:
            area = bool(es_area(base))
        except Exception:
            area = False
    return min(MAX_FACTOR, f * (pasiva["area"] if area else pasiva["uno"]))


def aplicar(valores: dict, destino: str, es_area=None) -> tuple[dict, dict]:
    """(valores con las pasivas aplicadas, motivos por carta)."""
    if not destino:
        return valores, {}
    salida, motivos = {}, {}
    for nombre, valor in valores.items():
        f = factor(nombre, destino, es_area)
        salida[nombre] = valor * f
        if f != 1.0:
            motivos[nombre] = [f"pasiva x{f:.2f}"]
    return salida, motivos

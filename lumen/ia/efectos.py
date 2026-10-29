"""Lector de efectos (pieza 1 de IA.md): del texto del juego (ingles, el del cliente de PC) a efectos y
mecanicas que el bot entiende.

- ``efectos(texto)``: una habilidad, pasiva o talento de un heroe -> [Efecto]. P. ej. Raining Blades
  ("Inflicts Cleave damage ... equal to 220% of Attack on one enemy, then decreases their Attack-related
  stats by 20% for 1 turn(s)") -> dano 220 % a uno (cleave) + debuff de ataque 20 % 1 turno.
- ``mecanicas(texto)``: un patron o pasiva de un jefe (Enemy Info) -> [Mecanica], cada una con lo que la
  vence o aprovecha (``contra``): Torrent -> "ulti", Inmortalidad por secuencia -> "secuencia_atributos"...
- ``no_entendido(texto)``: las frases de las que no salio nada, para ampliar las tablas con textos reales.

Las reglas son tablas (``REGLAS_HEROE``, ``REGLAS_JEFE``) de expresiones regulares: para entender una frase
nueva basta con anadir una fila y una prueba en pruebas/test_efectos.py con el texto real.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field

# ------------------------------------------------------------------ modelos


@dataclass(frozen=True)
class Efecto:
    tipo: str  # dano, debuff, buff, quitar_postura, curar, limpiar, escudo, aturdir, orbes, ignora_evasion...
    valor: float | None = None  # en % (220 = 220 % del ataque)
    objetivo: str = ""  # uno, todos, aliados, aliado, si_mismo
    turnos: int | None = None
    detalle: str = ""  # el stat ("attack"), "cleave", "ignora_defensa"...


@dataclass(frozen=True)
class Mecanica:
    tipo: str  # torrent, inmortalidad, reduccion_dano_atributo, proteccion, evasion, postura, bloqueo...
    contra: tuple[str, ...] = ()  # lo que la vence o aprovecha: "ulti", "mismo_atributo", "limpiar"...
    detalle: str = ""
    depende: str = ""  # otra mecanica de la que sale esta (la curacion del ciervo depende del Torrent)


# ------------------------------------------------------------------ frases
_SEPARADORES = re.compile(r"(?<=[.;])\s+|,?\s+then\s+|\s+and\s+(?=(?:inflicts?|deals?|decreases?|increases?|"
                          r"removes?|restores?|recovers?|grants?|stuns?|fills?|ignores?)\b)", re.I)


def frases(texto: str) -> list[str]:
    """El texto partido en acciones ("..., then ...", ". ", "and <verbo>")."""
    texto = re.sub(r"\s+", " ", (texto or "").replace("\n", " ")).strip()
    return [f.strip(" .,;") for f in _SEPARADORES.split(texto) if f and f.strip(" .,;")]


def _numero(m: re.Match, grupo: str) -> float | None:
    v = m.groupdict().get(grupo)
    return float(v) if v else None


def _objetivo(frase: str) -> str:
    f = frase.lower()
    if re.search(r"\ball enemies\b", f):
        return "todos"
    if re.search(r"\b(one|an|a single|the) enemy\b|\btheir\b|\btarget", f):
        return "uno"
    if re.search(r"\ball allies\b|\ballies'?\b", f):
        return "aliados"
    if re.search(r"\b(an|one) ally\b", f):
        return "aliado"
    if re.search(r"\b(itself|himself|herself|own|the hero's)\b", f):
        return "si_mismo"
    return ""


def _turnos(frase: str) -> int | None:
    m = re.search(r"for (\d+) turn", frase, re.I)
    return int(m.group(1)) if m else None


def _stat(texto: str) -> str:
    t = texto.lower().replace("-related stats", "").replace(" related stats", "").strip()
    return re.sub(r"^(their|its|the target's|enemies'|all allies'|allies'|the hero's|own)\s+", "", t)


# ------------------------------------------------------------------ heroes
def _dano(m: re.Match, frase: str) -> list[Efecto]:
    f = frase.lower()
    detalles = [d for d, clave in (("cleave", "cleave"), ("ignora_defensa", "ignor"), ("critico", "crit damage"))
                if clave in f and not (d == "critico" and "does not activate crit" in f)]
    valores = [float(v) for v in re.findall(r"(\d{2,4})\s*%\s*of\s*(?:their\s+|its\s+)?(?:attack|atk)", f)]
    return [Efecto("dano", v, _objetivo(frase), None, ",".join(detalles)) for v in valores]


def _cambio(tipo: str):
    def construir(m: re.Match, frase: str) -> list[Efecto]:
        return [Efecto(tipo, _numero(m, "pct"), _objetivo(frase), _turnos(frase), _stat(m.group("stat")))]
    return construir


def _simple(tipo: str, con_valor: bool = False):
    def construir(m: re.Match, frase: str) -> list[Efecto]:
        return [Efecto(tipo, _numero(m, "pct") if con_valor else None, _objetivo(frase), _turnos(frase))]
    return construir


REGLAS_HEROE: list[tuple[re.Pattern, Callable[[re.Match, str], list[Efecto]]]] = [
    (re.compile(r"(?:inflict(?:s|ing)?|deal(?:s|ing)?)\b.*?damage.*?\d+\s*%\s*of\s*(?:their\s+|its\s+)?(?:attack|atk)"
                r"|^\d+\s*%\s*of\s*(?:their\s+|its\s+)?attack\s+again", re.I), _dano),
    (re.compile(r"decreases?\s+(?P<stat>[\w'\- ]+?)\s+by\s+(?P<pct>\d+)\s*%", re.I), _cambio("debuff")),
    (re.compile(r"increases?\s+(?P<stat>[\w'\- ]+?)\s+by\s+(?P<pct>\d+)\s*%", re.I), _cambio("buff")),
    (re.compile(r"(?:removes?|ignores?|nullif(?:y|ies))\b.*\bstance", re.I), _simple("quitar_postura")),
    (re.compile(r"(?:removes?|cleanses?)\b.*\bdebuffs?", re.I), _simple("limpiar")),
    (re.compile(r"(?:restores?|recovers?)\s+(?:\w+\s+)*?hp\b(?:.*?(?P<pct>\d+)\s*%)?", re.I), _simple("curar", True)),
    (re.compile(r"\b(?:barrier|shield)\b", re.I), _simple("escudo")),
    (re.compile(r"\bstuns?\b|\bpetrif|\bfreezes?\b", re.I), _simple("aturdir")),
    (re.compile(r"ultimate move gauge.*?(?P<pct>\d+)\s*orb|fills?.*ultimate move gauge", re.I), _simple("orbes", True)),
    (re.compile(r"cannot be evaded|ignores?\s+evasion", re.I), _simple("ignora_evasion")),
]


def efectos(texto: str) -> list[Efecto]:
    """Los efectos de una habilidad, pasiva o talento (en el orden del texto)."""
    salida: list[Efecto] = []
    for frase in frases(texto):
        for patron, construir in REGLAS_HEROE:
            m = patron.search(frase)
            if m:
                for e in construir(m, frase):
                    if not e.objetivo and salida:  # "then 100% of Attack again": al mismo de antes
                        e = Efecto(e.tipo, e.valor, salida[-1].objetivo, e.turnos, e.detalle)
                    salida.append(e)
    return salida


# ------------------------------------------------------------------ jefes
def _contra_de(nombre: str, texto: str) -> tuple[str, ...]:
    """Lo que vence a un estado con nombre (Torrent...) segun el propio texto: "removed when ... Ultimate"."""
    t = texto.lower()
    contra = []
    if re.search(rf"{nombre}.*removed when.*ultimate move|ultimate move.*removes?.*{nombre}", t):
        contra.append("ulti")
    return tuple(contra)


def _atributos(texto: str) -> tuple[str, ...]:
    t = texto.lower()
    if "sequence of attributes" in t or "certain sequence" in t:
        return ("secuencia_atributos",)
    if "same attribute" in t:
        return ("mismo_atributo",)
    return ()


REGLAS_JEFE: list[tuple[re.Pattern, Callable[[re.Match, str], Mecanica]]] = [
    (re.compile(r"\btorrent\b", re.I), lambda m, t: Mecanica("torrent", _contra_de("torrent", t) or ("ulti",))),
    (re.compile(r"\bimmortality\b", re.I), lambda m, t: Mecanica("inmortalidad", _atributos(t) or ("golpes",))),
    (re.compile(r"damage taken decrease", re.I),
     lambda m, t: Mecanica("reduccion_dano_atributo", _atributos(t) or ("atributo_fuerte",))),
    (re.compile(r"attribute defense", re.I), lambda m, t: Mecanica("defensa_atributo", ("dano",), "cae con la vida")),
    (re.compile(r"(\w+)'s protection", re.I), lambda m, t: Mecanica("proteccion", _atributos(t), m.group(1))),
    (re.compile(r"\bevasion\b", re.I), lambda m, t: Mecanica("evasion", ("ignora_evasion", "ulti"))),
    (re.compile(r"\bstance\b", re.I), lambda m, t: Mecanica("postura", ("quitar_postura",))),
    (re.compile(r"block(?:s|ed)? skill|skill seal|disables? skills", re.I), lambda m, t: Mecanica("bloqueo", ("limpiar",))),
    (re.compile(r"recovers? hp equal to (\d+)\s*% of the damage dealt to enemies with (\w+)", re.I),
     lambda m, t: Mecanica("curacion_jefe", _contra_de(m.group(2).lower(), t) or ("quitar_" + m.group(2).lower(),),
                           f"{m.group(1)} % del dano a quien tenga {m.group(2)}", m.group(2).lower())),
    (re.compile(r"crit (chance|damage).*for every orb.*ultimate move gauge", re.I),
     lambda m, t: Mecanica("bonus_por_orbes", ("cargar_ulti",), f"critico ({m.group(1).lower()})")),
]


def mecanicas(texto: str) -> list[Mecanica]:
    """Las mecanicas de un patron o pasiva de jefe (cada tipo una vez, en el orden en que aparecen)."""
    encontradas: dict[str, tuple[int, Mecanica]] = {}
    for patron, construir in REGLAS_JEFE:
        m = patron.search(texto or "")
        if m:
            mec = construir(m, texto)
            if mec.tipo not in encontradas:
                encontradas[mec.tipo] = (m.start(), mec)
    # "Recovers HP ... to enemies with Torrent": la curacion manda; el Torrent ya va en su "contra".
    if "curacion_jefe" in encontradas and "torrent" in encontradas and len(frases(texto)) == 1:
        encontradas.pop("torrent")
    return [mec for _, mec in sorted(encontradas.values(), key=lambda x: x[0])]


def jefe(textos: list[str]) -> list[Mecanica]:
    """Las mecanicas de todos los textos de un jefe (patrones y pasivas de sus fases) juntas: si una depende
    de otra (la curacion por el Torrent), toma su contramedida (quitar el Torrent = usar la ulti)."""
    todas: list[Mecanica] = []
    for texto in textos:
        for mec in mecanicas(texto):
            if mec not in todas:
                todas.append(mec)
    por_tipo = {m.tipo: m for m in todas}
    salida = []
    for mec in todas:
        base = por_tipo.get(mec.depende)
        if base and base.contra:
            mec = Mecanica(mec.tipo, base.contra, mec.detalle, mec.depende)
        salida.append(mec)
    return salida


# ------------------------------------------------------------------ cobertura
def no_entendido(texto: str, jefe: bool = False) -> list[str]:
    """Frases de las que no salio ningun efecto (o mecanica): para ampliar las tablas."""
    if jefe:
        return [f for f in frases(texto) if not mecanicas(f)]
    return [f for f in frases(texto) if not efectos(f)]


@dataclass
class Informe:
    entendidas: int = 0
    total: int = 0
    pendientes: list[str] = field(default_factory=list)

    @property
    def cobertura(self) -> float:
        return 100 * self.entendidas / self.total if self.total else 0.0


def cobertura(textos: list[str]) -> Informe:
    """Cuantas frases de una lista de textos (p. ej. todas las cartas capturadas) entiende el lector."""
    inf = Informe()
    for texto in textos:
        for frase in frases(texto):
            inf.total += 1
            if efectos(frase):
                inf.entendidas += 1
            else:
                inf.pendientes.append(frase)
    return inf


# ------------------------------------------------------------------ en el PC
def textos_capturados() -> list[str]:
    """Los textos de todas las cartas de la captura de heroes de esta PC (capturas/heroes/catalogo.yaml)."""
    from lumen.valor_cartas import CATALOGO_TEXTOS

    import yaml

    if not CATALOGO_TEXTOS.is_file():
        return []
    catalogo = yaml.safe_load(CATALOGO_TEXTOS.read_text(encoding="utf-8")) or {}
    return [c["texto"] for h in catalogo.values() for c in (h or {}).get("cartas") or [] if c.get("texto")]


if __name__ == "__main__":  # py -m lumen.ia.efectos: cuanto entiende el lector de los textos capturados
    from collections import Counter

    informe = cobertura(textos_capturados())
    print(f"Entiende {informe.entendidas} de {informe.total} frases ({informe.cobertura:.0f} %).")
    for frase, veces in Counter(informe.pendientes).most_common(40):
        print(f"{veces:>4}  {frase}")

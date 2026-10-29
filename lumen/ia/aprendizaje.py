"""Aprender solo (pieza 6 de IA.md): el bot ajusta su forma de jugar con sus propias peleas.

Que ajusta: los parametros del juego inteligente (lumen/inteligencia.py, PARAMS_DEFECTO), cada uno con
pocos valores razonables (PARAMETROS). Cada pelea se juega con una "configuracion" y el diario
(lumen/ia/diario.py) la guarda junto al resultado. De ahi sale todo; no hay mas estado:

- Base: la configuracion que mas victorias saca por hora en ese destino (contando el tiempo de las
  derrotas y reinicios). Una variante solo pasa a ser la base si tiene al menos MIN_PELEAS peleas y gana
  un MEJORA (5 %) mas por hora que la base actual: asi no cambia por suerte.
- Explorar: 1 de cada 10 peleas (EXPLORAR) prueba una variante que cambia UN parametro UN paso respecto a
  la base (nunca algo disparatado), empezando por la menos probada.
- Descartar: una variante con 3 peleas o mas que gana menos de la mitad, o que va un 30 % mas lenta que la
  base, no se vuelve a probar.

Se puede apagar por modo ("Aprender solo" en las opciones): entonces juega siempre con la base aprendida.
"""

import json
import random
from dataclasses import dataclass

from lumen.inteligencia import PARAMS_DEFECTO

PARAMETROS: dict[str, tuple[float, ...]] = {  # valores posibles, de menos a mas (el de siempre en medio)
    "peso_futuro": (0.3, 0.45, 0.6),  # cuanto cuenta guardar cartas para el turno siguiente
    "valor_ulti": (3.0, 4.0, 5.0),  # cuanto vale jugar una ulti frente a una carta normal
    "solo_area_resto": (0.1, 0.2, 0.35),  # en fases de "solo area", cuanto vale una carta de un objetivo
}
DEFECTO = {k: PARAMS_DEFECTO[k] for k in PARAMETROS}
EXPLORAR = 0.1
MIN_PELEAS = 5
MEJORA = 1.05
DESCARTAR_TASA = 50.0  # % de victorias
DESCARTAR_LENTA = 0.7  # victorias por hora frente a la base
NOMBRES = {"peso_futuro": "guardar para el turno siguiente", "valor_ulti": "valor de la ulti",
           "solo_area_resto": "cartas de un objetivo en fases de área"}


def clave(config: dict) -> str:
    return json.dumps({k: config[k] for k in sorted(config)}, sort_keys=True)


@dataclass
class Cifras:
    peleas: int = 0
    victorias: int = 0
    segundos: float = 0.0

    @property
    def tasa(self) -> float:
        return 100 * self.victorias / self.peleas if self.peleas else 0.0

    @property
    def por_hora(self) -> float:
        return self.victorias / (self.segundos / 3600) if self.segundos > 0 else 0.0


def cifras(peleas: list[dict]) -> dict[str, Cifras]:
    """Por configuracion: peleas terminadas, victorias y tiempo total (las abandonadas no cuentan)."""
    salida: dict[str, Cifras] = {}
    for p in peleas:
        if not p.get("config") or p.get("resultado") not in ("victoria", "derrota", "reinicio"):
            continue
        c = salida.setdefault(clave(p["config"]), Cifras())
        c.peleas += 1
        c.victorias += p["resultado"] == "victoria"
        c.segundos += float(p.get("duracion") or 0)
    return salida


def base(peleas: list[dict]) -> dict:
    """La configuracion con la que jugar: la de siempre, salvo que otra haya demostrado ser mejor."""
    datos = cifras(peleas)
    mejor, mejor_cifras = dict(DEFECTO), datos.get(clave(DEFECTO))
    if mejor_cifras is None or mejor_cifras.peleas < MIN_PELEAS:
        return mejor  # primero hay que conocer bien la de siempre
    for k, c in datos.items():
        if c.peleas >= MIN_PELEAS and c.por_hora > mejor_cifras.por_hora * MEJORA:
            mejor, mejor_cifras = {**DEFECTO, **json.loads(k)}, c
    return mejor


def variantes(config: dict) -> list[dict]:
    """Las que cambian un solo parametro un solo paso."""
    salida = []
    for nombre, valores in PARAMETROS.items():
        i = valores.index(config[nombre]) if config[nombre] in valores else valores.index(DEFECTO[nombre])
        for j in (i - 1, i + 1):
            if 0 <= j < len(valores):
                salida.append({**config, nombre: valores[j]})
    return salida


def descartada(c: Cifras | None, de_la_base: Cifras | None) -> bool:
    if c is None or c.peleas < 3:
        return False
    lenta = de_la_base is not None and de_la_base.peleas >= MIN_PELEAS and c.por_hora < de_la_base.por_hora * DESCARTAR_LENTA
    return c.tasa < DESCARTAR_TASA or lenta


def elegir(peleas: list[dict], explorar: bool = True, rng: random.Random | None = None) -> tuple[dict, bool]:
    """(configuracion para la proxima pelea, si es una prueba)."""
    rng = rng or random
    actual = base(peleas)
    if not explorar or rng.random() >= EXPLORAR:
        return actual, False
    datos = cifras(peleas)
    de_la_base = datos.get(clave(actual))
    candidatas = [v for v in variantes(actual) if not descartada(datos.get(clave(v)), de_la_base)]
    if not candidatas:
        return actual, False
    menos = min((datos.get(clave(v)) or Cifras()).peleas for v in candidatas)
    return rng.choice([v for v in candidatas if (datos.get(clave(v)) or Cifras()).peleas == menos]), True


def diferencia(config: dict) -> str:
    """'valor de la ulti 5' (lo que cambia respecto a lo de siempre), o '' si es lo de siempre."""
    return ", ".join(f"{NOMBRES[k]} {config[k]:g}" for k in PARAMETROS if config.get(k) != DEFECTO[k])


def _coma(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def texto(peleas: list[dict]) -> str:
    """Una o dos lineas para el diario: con que juega ahora y que ha probado."""
    actual = base(peleas)
    datos = cifras(peleas)
    c = datos.get(clave(actual)) or Cifras()
    cambios = diferencia(actual)
    lineas = [f"Aprendizaje: juega {'con ' + cambios if cambios else 'como siempre'}"
              + (f" ({c.peleas} peleas, {_coma(c.por_hora)} victorias/h)" if c.peleas else "")]
    probadas = [(k, v) for k, v in datos.items() if k != clave(actual)]
    if probadas:
        de_la_base = datos.get(clave(actual))
        partes = []
        for k, v in sorted(probadas, key=lambda kv: -kv[1].peleas)[:3]:
            estado = " ✗" if descartada(v, de_la_base) else ""
            partes.append(f"{diferencia({**DEFECTO, **json.loads(k)}) or 'lo de siempre'}: {v.peleas} peleas, "
                          f"{_coma(v.por_hora)}/h{estado}")
        lineas.append("Probado: " + " · ".join(partes))
    return "\n".join(lineas)

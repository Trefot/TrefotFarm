"""Diario de peleas (pieza 5 de IA.md): cada decision del bot con su contexto y como acabo la pelea.

Una linea por pelea en logs/diario/<destino>.jsonl (en esta PC, no va en git):
  {"destino", "inicio", "version", "equipo", "resultado": victoria | derrota | reinicio | abandonada,
   "fase_final", "duracion", "turnos": [{"t", "fase", "turno", "accion", "mano", "jugada", "razones"}],
   "notas": ["Reinicio: F1T1: falta la postura de Thonar", ...]}

Sirve para dos cosas: que el bot aprenda solo (pieza 6: que jugadas acaban en victorias rapidas) y que
el jugador se lo pase al analista (Claude en las sesiones, sin coste extra): ``texto`` lo resume en pocas
lineas, y la orden "diario" del movil lo envia.
"""

import json
import time
from collections import Counter
from pathlib import Path

import lumen
from lumen.rutas import LOGS

CARPETA = LOGS / "diario"


def _jugada(mano: list, eleccion) -> list:
    """("jugar", carta) o ("mover", origen, destino) con los nombres de las cartas."""
    def nombre(i):
        c = mano[i] if 0 <= i < len(mano) else None
        return (c.nombre or str(c)) if c is not None else "?"

    if isinstance(eleccion, tuple):
        return ["mover", nombre(eleccion[0]), nombre(eleccion[1])]
    return ["jugar", nombre(eleccion)]


class Diario:
    """El diario de un destino. Se abre una pelea con ``empezar`` y se cierra (y guarda) con ``terminar``."""

    def __init__(self, destino: str, carpeta: Path | None = None):
        self.destino = destino
        self.carpeta = carpeta or CARPETA
        self.pelea: dict | None = None

    def empezar(self, equipo: list[str] | None = None, **extra):
        self.pelea = {"destino": self.destino, "inicio": time.time(), "version": lumen.__version__,
                      "equipo": list(equipo or []), "turnos": [], "notas": [], **extra}

    def decision(self, fase, turno, accion: int, mano: list, eleccion, razones: dict | None = None):
        if self.pelea is None:
            return
        jugada = _jugada(mano, eleccion)
        paso = {"t": round(time.time() - self.pelea["inicio"], 1), "fase": fase, "turno": turno, "accion": accion,
                "mano": [str(c) for c in mano], "jugada": jugada}
        motivos = {n: r for n, r in (razones or {}).items() if n.split("@")[0] in {j.split("@")[0] for j in jugada[1:]}}
        if motivos:
            paso["razones"] = motivos
        self.pelea["turnos"].append(paso)

    def nota(self, texto: str):
        if self.pelea is not None:
            self.pelea["notas"].append(texto)

    def terminar(self, resultado: str, fase=None) -> dict | None:
        """Cierra la pelea y la guarda. Devuelve lo guardado (None si no habia pelea abierta)."""
        if self.pelea is None:
            return None
        pelea, self.pelea = self.pelea, None
        pelea.update(resultado=resultado, fase_final=fase, duracion=round(time.time() - pelea["inicio"], 1))
        try:
            self.carpeta.mkdir(parents=True, exist_ok=True)
            with (self.carpeta / f"{self.destino}.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(pelea, ensure_ascii=False) + "\n")
        except OSError:
            pass  # el diario nunca debe parar el bot
        return pelea


# ------------------------------------------------------------------ leer
def leer(destino: str | None = None, limite: int = 200, carpeta: Path | None = None) -> list[dict]:
    """Las ultimas peleas (la mas reciente primero), de un destino o de todos."""
    carpeta = carpeta or CARPETA
    archivos = [carpeta / f"{destino}.jsonl"] if destino else sorted(carpeta.glob("*.jsonl"))
    peleas = []
    for archivo in archivos:
        if not archivo.is_file():
            continue
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            try:
                peleas.append(json.loads(linea))
            except json.JSONDecodeError:
                continue
    return sorted(peleas, key=lambda p: -p.get("inicio", 0))[:limite]


def resumen(peleas: list[dict]) -> dict:
    """Cifras de un grupo de peleas: resultados, tiempo por victoria, donde se pierde y que se juega al ganar."""
    cuenta = Counter(p.get("resultado") for p in peleas)
    victorias = [p for p in peleas if p.get("resultado") == "victoria"]
    terminadas = sum(cuenta[r] for r in ("victoria", "derrota", "reinicio"))
    jugadas = {}
    for p in victorias:
        for paso in p.get("turnos") or []:
            if paso.get("jugada", [""])[0] == "jugar":
                jugadas.setdefault(paso.get("fase"), Counter())[paso["jugada"][1].split("@")[0]] += 1
    return {
        "peleas": len(peleas),
        "victorias": cuenta["victoria"], "derrotas": cuenta["derrota"], "reinicios": cuenta["reinicio"],
        "tasa": 100 * cuenta["victoria"] / terminadas if terminadas else 0.0,
        "segundos_victoria": sum(p.get("duracion", 0) for p in victorias) / len(victorias) if victorias else 0.0,
        "derrotas_por_fase": Counter(p.get("fase_final") for p in peleas if p.get("resultado") == "derrota"),
        "motivos_reinicio": Counter(n for p in peleas if p.get("resultado") == "reinicio" for n in p.get("notas") or []),
        "jugadas_al_ganar": jugadas,
    }


def _tiempo(segundos: float) -> str:
    m, s = divmod(int(segundos), 60)
    return f"{m}:{s:02d}"


def texto(destino: str | None = None, nombre: str = "", ultimas: int = 30, carpeta: Path | None = None) -> str:
    """El diario resumido en pocas lineas: para el movil y para pasarselo al analista."""
    peleas = leer(destino, ultimas, carpeta)
    titulo = f"Lumen Farm {lumen.__version__} · Diario · {nombre or destino or 'todo'}"
    if not peleas:
        return f"{titulo}\nTodavía no hay peleas en el diario."
    r = resumen(peleas)
    lineas = [f"{titulo} · últimas {r['peleas']} peleas",
              f"Victorias {r['victorias']} · derrotas {r['derrotas']} · reinicios {r['reinicios']} · "
              f"gana el {r['tasa']:.0f} %" + (f" · {_tiempo(r['segundos_victoria'])} por victoria" if r["victorias"] else "")]
    if r["derrotas_por_fase"]:
        lineas.append("Derrotas por fase: " + " · ".join(f"F{f}: {n}" for f, n in sorted(r["derrotas_por_fase"].items(),
                                                                                        key=lambda x: (x[0] is None, x[0]))))
    for motivo, n in r["motivos_reinicio"].most_common(3):
        lineas.append(f"Reinicio ×{n}: {motivo}")
    for fase, cartas in sorted(r["jugadas_al_ganar"].items(), key=lambda x: (x[0] is None, x[0])):
        top = ", ".join(f"{c} ({n})" for c, n in cartas.most_common(3))
        lineas.append(f"Al ganar, F{fase}: {top}")
    return "\n".join(lineas)

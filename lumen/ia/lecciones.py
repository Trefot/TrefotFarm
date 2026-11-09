"""Lecciones de cada pelea (paso 5 de IA.md): aprender de UNA sola pelea, gane o pierda, para no repetir errores.

El usuario lo pidio asi (2026-11-09): no hace falta esperar muchas peleas, cada una ensena algo. Al terminar una
pelea (lumen/ia/diario.py la guarda con cada jugada, su fase y como acabo) se sacan lecciones por destino y fase:

- Victoria: las cartas que se jugaron en cada fase funcionaron. Si la fase salio en menos turnos que la mejor vez,
  valen un poco mas ahi (se refuerza lo que gana rapido).
- Derrota o reinicio: en la fase donde se perdio, las cartas de los ultimos turnos llevaron a perder: valen menos ahi
  la proxima vez. Si se perdio por tardar demasiado, en esa fase valen mas las de mas dano (area y ulti). Si el bot se
  quedo sin jugada (todo bloqueado), se apunta para avisar.
- Las peleas abandonadas (el jugador paro el bot) no ensenan nada.

Cada leccion es un multiplicador sobre el valor de una carta ("carta:heroe.carta") o de un tipo ("tipo:area",
"tipo:uno", "tipo:ulti") en esa fase, con limites (0,5-1,8) para que una mala racha no lo desordene. Se guarda en
logs/lecciones/<destino>.json (en esta PC) y lo usa el juego inteligente (Jugador.elegir) al valorar las cartas.
"""

import json
import threading
from pathlib import Path

from lumen.rutas import LOGS

CARPETA = LOGS / "lecciones"
MINIMO, MAXIMO = 0.5, 1.8
REFUERZO = 0.06  # victoria en menos turnos que la mejor vez
CASTIGO = 0.15  # cartas de los ultimos turnos antes de perder
CASTIGO_TIPO = 0.05
MAS_DANO = 0.10  # se perdio por tardar: area y ulti valen mas
TURNOS_CULPABLES = 2  # ultimos turnos de la fase perdida que se miran
_lock = threading.Lock()


_tasador = None


def es_area_por_defecto(nombre: str) -> bool:
    """Si la carta pega a todos (con el tasador del juego inteligente; se carga una vez)."""
    global _tasador
    if _tasador is None:
        from lumen import valor_cartas

        _tasador = valor_cartas.Tasador(1)
    return _tasador.es_area(nombre)


def _ruta(destino: str, carpeta: Path | None = None) -> Path:
    return (carpeta or CARPETA) / f"{destino}.json"


def cargar(destino: str, carpeta: Path | None = None) -> dict:
    ruta = _ruta(destino, carpeta)
    try:
        return json.loads(ruta.read_text(encoding="utf-8")) if ruta.is_file() else {}
    except (OSError, ValueError):
        return {}


def _guardar(destino: str, datos: dict, carpeta: Path | None = None) -> None:
    ruta = _ruta(destino, carpeta)
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass  # aprender nunca debe parar el bot


def _base(nombre: str) -> str:
    return (nombre or "").split("@")[0]


def _tipo(nombre: str, es_area=None) -> str:
    base = _base(nombre)
    if base.endswith(".ulti"):
        return "tipo:ulti"
    if es_area is not None:
        try:
            return "tipo:area" if es_area(base) else "tipo:uno"
        except Exception:
            return ""
    return ""


def _ajustar(fase_datos: dict, clave: str, delta: float, motivo: str) -> None:
    item = fase_datos.setdefault(clave, {"peso": 1.0, "veces": 0})
    item["peso"] = round(min(MAXIMO, max(MINIMO, item["peso"] + delta)), 3)
    item["veces"] = item.get("veces", 0) + 1
    item["motivo"] = motivo


def aprender(pelea: dict, es_area=None, carpeta: Path | None = None) -> list[str]:
    """Saca las lecciones de una pelea terminada (la que guarda el diario) y las guarda. Devuelve que aprendio, en
    frases para el registro. ``es_area``: nombre de carta -> si pega a todos (para las lecciones por tipo)."""
    resultado = pelea.get("resultado")
    destino = pelea.get("destino")
    if not destino or resultado not in ("victoria", "derrota", "reinicio"):
        return []
    # Solo las cartas reconocidas ("heroe.carta"): de una sin reconocer ("dibujo_2", "?") no se aprende nada
    jugadas = [t for t in pelea.get("turnos") or [] if (t.get("jugada") or [""])[0] == "jugar" and t.get("fase")
               and "." in _base(t["jugada"][1])]
    if not jugadas:
        return []
    frases = []
    with _lock:
        datos = cargar(destino, carpeta)
        fases = datos.setdefault("fases", {})
        mejores = datos.setdefault("mejores_turnos", {})
        if resultado == "victoria":
            por_fase: dict[int, list] = {}
            for t in jugadas:
                por_fase.setdefault(int(t["fase"]), []).append(t)
            for fase, lista in por_fase.items():
                turnos = len({t.get("turno") for t in lista})
                mejor = mejores.get(str(fase))
                if mejor is None or turnos < mejor:
                    mejores[str(fase)] = turnos
                    for t in lista:
                        _ajustar(fases.setdefault(str(fase), {}), "carta:" + _base(t["jugada"][1]), REFUERZO,
                                 f"gano la fase {fase} en {turnos} turnos")
                    frases.append(f"Fase {fase} en {turnos} turno(s): {'primera vez' if mejor is None else 'mejor que ' + str(mejor)}"
                                  "; refuerzo las cartas que jugué.")
        else:
            fase = int(pelea.get("fase_final") or jugadas[-1]["fase"])
            de_la_fase = [t for t in jugadas if int(t["fase"]) == fase]
            ultimos = sorted({t.get("turno") for t in de_la_fase})[-TURNOS_CULPABLES:]
            culpables = [t for t in de_la_fase if t.get("turno") in ultimos]
            datos_fase = fases.setdefault(str(fase), {})
            nombres = []
            for t in culpables:
                nombre = _base(t["jugada"][1])
                _ajustar(datos_fase, "carta:" + nombre, -CASTIGO, f"perdio en la fase {fase}")
                tipo = _tipo(nombre, es_area)
                if tipo:
                    _ajustar(datos_fase, tipo, -CASTIGO_TIPO, f"perdio en la fase {fase}")
                nombres.append(nombre.split(".")[0])
            notas = " ".join(pelea.get("notas") or []).lower()
            if "demasiado" in notas or "dura" in notas:
                for tipo in ("tipo:area", "tipo:ulti"):
                    _ajustar(datos_fase, tipo, MAS_DANO, f"en la fase {fase} se tardo demasiado")
                frases.append(f"Fase {fase}: tardé demasiado; la próxima priorizo área y ultis.")
            if "sin jugada" in notas or "bloque" in notas:
                datos.setdefault("avisos", []).append(f"fase {fase}: me quede sin jugada (todo bloqueado)")
                frases.append(f"Fase {fase}: me quedé sin jugada; lo apunto para no repetirlo.")
            frases.append(f"Perdí en la fase {fase}: valoro menos lo que jugué al final "
                          f"({', '.join(sorted(set(nombres))[:4])}).")
        datos["peleas"] = datos.get("peleas", 0) + 1
        _guardar(destino, datos, carpeta)
    return frases


def aplicar(valores: dict, destino: str, fase, es_area=None, carpeta: Path | None = None,
            datos: dict | None = None) -> tuple[dict, dict]:
    """(valores ajustados con lo aprendido en ese destino y fase, motivos por carta)."""
    if not destino or not fase:
        return valores, {}
    datos = datos if datos is not None else cargar(destino, carpeta)
    lecciones = (datos.get("fases") or {}).get(str(fase)) or {}
    if not lecciones:
        return valores, {}
    salida, motivos = {}, {}
    for nombre, valor in valores.items():
        factor = 1.0
        carta = lecciones.get("carta:" + _base(nombre))
        if carta:
            factor *= carta["peso"]
        tipo = _tipo(nombre, es_area)
        if tipo and tipo in lecciones:
            factor *= lecciones[tipo]["peso"]
        salida[nombre] = valor * factor
        if factor != 1.0:
            motivos[nombre] = [f"aprendido x{factor:.2f}"]
    return salida, motivos


def resumen(destino: str, carpeta: Path | None = None) -> str:
    """Lo aprendido en un destino, en pocas lineas (para el diario y el movil)."""
    datos = cargar(destino, carpeta)
    if not datos.get("fases"):
        return "Aún no he aprendido nada aquí."
    lineas = [f"Aprendido en {datos.get('peleas', 0)} pelea(s):"]
    for fase, lecciones in sorted(datos["fases"].items()):
        mejores = sorted(lecciones.items(), key=lambda kv: -kv[1]["peso"])
        arriba = [k.split(":", 1)[1] for k, v in mejores if v["peso"] > 1.0][:3]
        abajo = [k.split(":", 1)[1] for k, v in mejores if v["peso"] < 1.0][-3:]
        partes = []
        if arriba:
            partes.append("mejor: " + ", ".join(arriba))
        if abajo:
            partes.append("evito: " + ", ".join(abajo))
        lineas.append(f"Fase {fase}: " + ("; ".join(partes) if partes else "sin cambios"))
    return "\n".join(lineas)

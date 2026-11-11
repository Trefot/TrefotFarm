"""Memoria aislada por destino y equipo; operaciones administrativas reversibles."""

from functools import lru_cache, wraps
import hashlib
import math
import json
import re
import threading
import time
from pathlib import Path

from lumen import admin
from lumen.archivos import escribir_texto
from lumen.rutas import LOGS, RAIZ

CARPETA = LOGS / "perfiles_ia"
_lock = threading.RLock()


@lru_cache(maxsize=1)
def firma_conocimiento() -> str:
    huella = hashlib.sha256(b"perfiles-ia-v1")
    for nombre in (
        "personajes.yaml",
        "habilidades.yaml",
        "fichas.yaml",
        "jefes.yaml",
        "conocimiento.yaml",
    ):
        huella.update((RAIZ / "lumen" / "datos" / nombre).read_bytes())
    for nombre in (
        "inteligencia.py",
        "valor_cartas.py",
        "ia/decidir.py",
        "ia/efectos.py",
        "ia/estado.py",
    ):
        huella.update(nombre.encode())
        huella.update((RAIZ / "lumen" / nombre).read_bytes())
    return huella.hexdigest()[:16]


def equipo_clave(equipo) -> tuple[str, ...]:
    if not isinstance(equipo, (list, tuple, set)):
        return ()
    if not all(isinstance(p, str) and re.fullmatch(r"[a-z0-9_]+", p) for p in equipo):
        return ()
    claves = tuple(sorted(set(equipo)))
    return claves if 3 <= len(claves) <= 4 and len(claves) == len(equipo) else ()


def clave(destino: str, equipo) -> str | None:
    heroes = equipo_clave(equipo)
    if not heroes or not re.fullmatch(r"[a-z0-9_]+", destino or ""):
        return None
    return hashlib.sha256(
        json.dumps([destino, heroes, firma_conocimiento()]).encode()
    ).hexdigest()[:24]


def carpeta(destino: str, equipo) -> Path | None:
    identificador = clave(destino, equipo)
    return CARPETA / identificador if identificador else None


def _meta(destino, equipo):
    ruta = carpeta(destino, equipo)
    if ruta is None:
        return {}
    archivo = ruta / "perfil.json"
    if not archivo.is_file():
        return {}
    try:
        datos = json.loads(archivo.read_text(encoding="utf-8"))
        if not isinstance(datos, dict):
            raise ValueError("perfil no valido")
        return datos
    except (OSError, ValueError):
        return {
            "restaurando": True,
            "error": "Perfil ilegible: restaura una copia desde Laboratorio.",
        }


def preparar(destino: str, equipo) -> Path | None:
    ruta = carpeta(destino, equipo)
    if ruta is None:
        return None
    with _lock:
        archivo = ruta / "perfil.json"
        if not archivo.exists():
            escribir_texto(
                archivo,
                json.dumps(
                    {
                        "destino": destino,
                        "equipo": list(equipo_clave(equipo)),
                        "desde": 0,
                        "creado": time.time(),
                        "conocimiento": firma_conocimiento(),
                    },
                    ensure_ascii=False,
                ),
            )
    return ruta


def filtrar(peleas: list[dict], destino: str, equipo) -> list[dict]:
    heroes = equipo_clave(equipo)
    if not heroes:
        return []
    meta = _meta(destino, equipo)
    if meta.get("restaurando"):
        return []
    desde = meta.get("desde", 0)
    return [
        p
        for p in peleas
        if equipo_clave(p.get("equipo")) == heroes
        and (p.get("lecciones") or p.get("destino")) == destino
        and float(p.get("inicio") or 0) >= desde
        and p.get("calidad", "fiable") == "fiable"
        and p.get("conocimiento") == firma_conocimiento()
        and (
            not p.get("memoria_por_equipo")
            or any(t.get("confirmada") for t in p.get("turnos", []))
        )
    ]


def aprender(pelea: dict, es_area=None) -> list[str]:
    from lumen.ia import lecciones

    destino, equipo = pelea.get("destino", ""), pelea.get("equipo")
    if (
        pelea.get("calidad", "fiable") != "fiable"
        or pelea.get("conocimiento") != firma_conocimiento()
    ):
        return []
    with _lock:
        ruta = preparar(destino, equipo)
        if ruta is None:
            return []  # no inventar un equipo ni mezclar memoria global con un equipo desconocido
        if _meta(destino, equipo).get("restaurando"):
            return []
        if float(pelea.get("inicio") or 0) < _meta(destino, equipo).get("desde", 0):
            return []  # una pelea que empezo antes de restaurar/reiniciar no vuelve a contaminarlo
        return lecciones.aprender(pelea, es_area=es_area, carpeta=ruta)


def estado(destino: str, equipo) -> dict:
    from lumen.ia import lecciones

    ruta = carpeta(destino, equipo)
    if ruta is None:
        return {}
    with _lock:
        return {
            "perfil": _meta(destino, equipo),
            "lecciones": lecciones.cargar(destino, ruta),
        }


def _comprobar_libre(ocupado):
    from lumen.control import control

    if ocupado or control.ejecutando:
        raise RuntimeError(
            "Deten el bot, el plan y el analisis antes de cambiar su memoria."
        )


def _validar_lecciones(datos):
    if not isinstance(datos, dict) or not isinstance(datos.get("fases", {}), dict):
        raise ValueError("Lecciones no validas.")
    for fase in datos.get("fases", {}).values():
        if not isinstance(fase, dict):
            raise ValueError("Fase de lecciones no valida.")
        for item in fase.values():
            peso = item.get("peso") if isinstance(item, dict) else None
            if (
                not isinstance(peso, (int, float))
                or not math.isfinite(peso)
                or not 0.5 <= peso <= 1.8
            ):
                raise ValueError("Peso de leccion no valido.")


def _leer_snapshot(ruta: Path, destino: str, equipo) -> dict:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    if (
        datos.get("destino") != destino
        or equipo_clave(datos.get("equipo")) != equipo_clave(equipo)
        or not isinstance(datos.get("lecciones"), dict)
    ):
        raise ValueError("La copia no corresponde a este destino y equipo.")
    _validar_lecciones(datos["lecciones"])
    from lumen.ia import aprendizaje

    if not aprendizaje.valida(datos.get("parametros")):
        raise ValueError("Parametros de copia no validos.")
    # Solo se aceptan nuestros nombres generados; nunca un camino indicado por el archivo.
    return datos


def _copia(destino: str, equipo, ruta: Path) -> str:
    from lumen.ia import lecciones

    nombre = f"copia_{time.time_ns()}.json"
    datos = {
        "destino": destino,
        "equipo": list(equipo_clave(equipo)),
        "fecha": time.time(),
        "lecciones": lecciones.cargar(destino, ruta),
        "parametros": parametros(destino, equipo),
        "desde": _meta(destino, equipo).get("desde", 0),
    }
    escribir_texto(
        ruta / nombre, json.dumps(datos, ensure_ascii=False, indent=2), respaldo=False
    )
    return nombre


def copias(destino: str, equipo) -> list[str]:
    admin.exigir()
    ruta = carpeta(destino, equipo)
    return (
        sorted((p.name for p in ruta.glob("copia_*.json")), reverse=True)
        if ruta
        else []
    )


def guardar_copia(destino: str, equipo, *, ocupado=False) -> str:
    admin.exigir()
    _comprobar_libre(ocupado)
    with _lock:
        ruta = preparar(destino, equipo)
        if ruta is None:
            raise ValueError("Indica un equipo completo de 3 o 4 heroes distintos.")
        return _copia(destino, equipo, ruta)


def restaurar(destino: str, equipo, nombre: str | None, *, ocupado=False) -> str:
    admin.exigir()
    _comprobar_libre(ocupado)
    with _lock:
        ruta = preparar(destino, equipo)
        if ruta is None:
            raise ValueError("Indica un equipo completo de 3 o 4 heroes distintos.")
        if nombre is not None and not re.fullmatch(r"copia_\d+\.json", nombre):
            raise ValueError("Nombre de copia no valido.")
        from lumen.ia import aprendizaje

        snapshot = (
            _leer_snapshot(ruta / nombre, destino, equipo)
            if nombre
            else {"lecciones": {}, "parametros": dict(aprendizaje.DEFECTO)}
        )
        copia = _copia(destino, equipo, ruta)
        # El corte evita que las estadisticas antiguas vuelvan a elegir una politica que se acaba de retirar.
        meta = {
            "destino": destino,
            "equipo": list(equipo_clave(equipo)),
            "desde": time.time(),
            "restaurada": nombre or "base",
            "parametros": snapshot["parametros"],
        }
        escribir_texto(
            ruta / "perfil.json",
            json.dumps({**meta, "restaurando": True}, ensure_ascii=False),
        )
        escribir_texto(
            ruta / f"{destino}.json",
            json.dumps(snapshot["lecciones"], ensure_ascii=False),
        )
        escribir_texto(ruta / "perfil.json", json.dumps(meta, ensure_ascii=False))
        return copia


def habilitado(destino, equipo) -> bool:
    from lumen.ia import lecciones

    ruta = carpeta(destino, equipo)
    if ruta is None or _meta(destino, equipo).get("restaurando"):
        return False
    try:
        _validar_lecciones(lecciones.cargar(destino, ruta))
    except ValueError:
        return False
    return True


def historia(destino, equipo):
    from lumen.ia import diario

    origen = (
        destino.rsplit("_f", 1)[0] + "_pisos1a3"
        if re.search(r"_f[123]$", destino)
        else destino
    )
    origen = re.sub(r"_(chaos|hell|extreme|hard|normal)$", "", origen)
    return filtrar(diario.leer(origen, 1000), destino, equipo)


def parametros(destino, equipo, peleas=None):
    from lumen.ia import aprendizaje

    meta = _meta(destino, equipo)
    if meta.get("restaurando"):
        return dict(aprendizaje.DEFECTO)
    inicial = meta.get("parametros")
    return aprendizaje.base(
        historia(destino, equipo) if peleas is None else peleas, inicial
    )


def elegir(peleas, destino, equipo, explorar=True):
    from lumen.ia import aprendizaje

    meta = _meta(destino, equipo)
    inicial = None if meta.get("restaurando") else meta.get("parametros")
    actual = parametros(destino, equipo, peleas)
    medidas = aprendizaje.cifras(peleas).get(aprendizaje.clave(actual))
    explorar = bool(
        explorar
        and equipo_clave(equipo)
        and medidas
        and medidas.peleas >= aprendizaje.MIN_PELEAS
    )
    opciones = {"explorar": explorar}
    if inicial is not None:
        opciones["inicial"] = inicial
    return aprendizaje.elegir(peleas, **opciones)


def lectura(funcion):
    @wraps(funcion)
    def protegida(*args, **kwargs):
        # Serializa comparaciones y modificaciones de memoria, incluso desde llamadas directas.
        with _lock:
            return funcion(*args, **kwargs)

    return protegida


def texto_modo(modo_id):
    from lumen.ia import lecciones

    partes = []
    base = modo_id.removesuffix("_pisos1a3")
    for ruta in sorted(CARPETA.glob("*/perfil.json")):
        try:
            meta = json.loads(ruta.read_text(encoding="utf-8"))
            destino, equipo = meta.get("destino", ""), meta.get("equipo", [])
            pertenece = (
                destino == modo_id
                or destino.startswith(modo_id + "_")
                or (
                    base != modo_id
                    and re.fullmatch(re.escape(base) + r"_f[123]", destino)
                )
            )
            if pertenece and carpeta(destino, equipo) == ruta.parent:
                partes.append(
                    f"{destino} · {', '.join(equipo)}\n"
                    + lecciones.resumen(destino, ruta.parent)
                )
        except (OSError, ValueError, AttributeError):
            continue
    return "\n\n".join(partes)

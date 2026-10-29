"""Recompensas: foto de la pantalla de Victory de cada pelea y lo que salio en ella.

Cada victoria guarda una foto en recompensas/<AAAA-MM-DD>/ y una linea en recompensas/indice.jsonl
con lo leido por lumen/botin.py: {"objetos": {id_objeto: cantidad}, "oro": int}.
Las fotos de antes de que existiera la lectura se analizan con ``reanalizar_pendientes``.
"""

import json
import threading
import time
from pathlib import Path

import numpy as np

from lumen import botin, juego, premios
from lumen.rutas import RAIZ
from lumen.vision import guardar_imagen, leer_imagen

CARPETA = RAIZ / "recompensas"
INDICE = CARPETA / "indice.jsonl"
_lock = threading.Lock()
# Version de la lectura del botin: al subirla, las fotos leidas con una anterior se vuelven a leer solas
# (2: cantidades con los digitos del juego y fotos sin boton OK fuera, 0.3.0; 3: el "3" sobre fondo claro, 0.7.1).
LECTURA = 3


def _analizar(pantalla) -> dict:
    try:
        if not juego.ok.esta(pantalla):
            # Sin el boton OK no es la pantalla de premios: las fotos de Indura de antes de la 0.2.3 se
            # hicieron en "HEART DESTROYED" y el bot guardo como objetos 14 trozos del fondo de lava.
            return {"objetos": {}, "oro": None, "sin_premios": True}
        return botin.analizar(pantalla)
    except Exception:  # una lectura fallida nunca debe parar el bot
        return {"objetos": {}, "oro": None, "error_lectura": True}


def guardar(pantalla: np.ndarray, *, modo: str, nombre_modo: str, sesion: float, victoria: int) -> Path:
    ahora = time.time()
    carpeta = CARPETA / time.strftime("%Y-%m-%d", time.localtime(ahora))
    ruta = carpeta / f"{time.strftime('%H%M%S', time.localtime(ahora))}_{modo}_v{victoria}.png"
    guardar_imagen(ruta, pantalla)
    registro = {
        "ruta": ruta.relative_to(CARPETA).as_posix(),
        "fecha": ahora,
        "modo": modo,
        "nombre_modo": nombre_modo,
        "sesion": sesion,
        "victoria": victoria,
        **_analizar(pantalla),
        "analizado": True,
        "lectura": LECTURA,
    }
    with _lock:
        CARPETA.mkdir(parents=True, exist_ok=True)
        with INDICE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    return ruta


def _leer_indice() -> list[dict]:
    if not INDICE.is_file():
        return []
    registros = []
    for linea in INDICE.read_text(encoding="utf-8").splitlines():
        try:
            registros.append(json.loads(linea))
        except json.JSONDecodeError:
            continue
    return registros


def leer() -> list[dict]:
    """Registros cuya foto todavia existe, el mas reciente primero."""
    registros = []
    for r in _leer_indice():
        r["ruta_completa"] = CARPETA / r["ruta"]
        if r["ruta_completa"].is_file():
            registros.append(r)
    return registros[::-1]


def pendiente(registro: dict) -> bool:
    """Foto sin leer, o leida con una version anterior de la lectura."""
    return not registro.get("analizado") or registro.get("lectura", 1) < LECTURA


def reanalizar_pendientes(todas: bool = False) -> int:
    """Lee el botin de las fotos que aun no se analizaron (o de todas). Devuelve cuantas analizo."""
    with _lock:
        registros = _leer_indice()
        hechas = 0
        for r in registros:
            if not pendiente(r) and not todas:
                continue
            pantalla = leer_imagen(CARPETA / r["ruta"])
            if pantalla is None:
                continue
            r.pop("sin_premios", None)
            r.update(_analizar(pantalla))
            r["analizado"], r["lectura"] = True, LECTURA
            hechas += 1
        if hechas:
            INDICE.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in registros), encoding="utf-8")
        return hechas


def _reescribir_objetos(cambio) -> None:
    """Aplica ``cambio(objetos) -> objetos`` a todos los registros del indice."""
    with _lock:
        registros = _leer_indice()
        for r in registros:
            r["objetos"] = cambio(dict(r.get("objetos") or {}))
        INDICE.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in registros), encoding="utf-8")


def unir_objeto(origen: str, destino: str) -> None:
    """``origen`` era ``destino`` leido raro: desde ahora cuenta como el, tambien en lo ya guardado."""
    catalogo = botin.cargar_catalogo()
    catalogo.setdefault(origen, {})["unido_a"] = destino
    botin.guardar_catalogo(catalogo)

    def cambio(objetos):
        if origen in objetos:
            objetos[destino] = objetos.get(destino, 0) + objetos.pop(origen)
        return objetos

    _reescribir_objetos(cambio)


def descartar_objeto(oid: str) -> None:
    """No era un objeto (p. ej. un cofre a medio abrir): se quita de todo y no se vuelve a contar."""
    catalogo = botin.cargar_catalogo()
    catalogo.setdefault(oid, {})["descartado"] = True
    botin.guardar_catalogo(catalogo)
    _reescribir_objetos(lambda objetos: {k: v for k, v in objetos.items() if k != oid})


def unir_repetidos_de_galeria() -> int:
    """Objetos del botin vinculados al mismo objeto de la galeria (p. ej. uno leido de una foto movida):
    se unen al primero. Devuelve cuantos unio."""
    catalogo = botin.cargar_catalogo()
    primero: dict[str, str] = {}
    unidos = 0
    for oid in botin.visibles(catalogo):
        gid = (catalogo.get(oid) or {}).get("galeria")
        if not gid:
            continue
        if gid in primero:
            unir_objeto(oid, primero[gid])
            catalogo = botin.cargar_catalogo()
            catalogo[oid]["unido_auto"] = True  # union hecha por el bot (se deshace si el vinculo era malo)
            botin.guardar_catalogo(catalogo)
            unidos += 1
        else:
            primero[gid] = oid
    return unidos


def deshacer_uniones_malas() -> int:
    """Uniones hechas porque dos objetos tenian el mismo de la galeria, cuando uno de esos vinculos ya no
    vale (p. ej. el cubo gris tomado por Blue Magic Essence): se separan y se releen las fotos para que
    cada uno recupere sus cantidades. Devuelve cuantas deshizo.
    Solo las que hizo el bot ("unido_auto"): las que une el jugador a mano se respetan siempre."""
    catalogo = botin.cargar_catalogo()
    deshechas = 0
    for oid, datos in catalogo.items():
        destino = (datos or {}).get("unido_a")
        gid = (datos or {}).get("galeria")
        if (datos or {}).get("unido_auto") and destino and gid and (catalogo.get(destino) or {}).get("galeria") != gid:
            datos.pop("unido_a", None)
            datos.pop("unido_auto", None)
            deshechas += 1
    if deshechas:
        botin.guardar_catalogo(catalogo)
        reanalizar_pendientes(todas=True)
    return deshechas


def horas_de(registros: list[dict], sesiones_historial: list[dict]) -> float:
    """Horas farmeando en las sesiones de esos registros (del historial; si falta, de la primera
    a la ultima foto)."""
    por_inicio = {round(s.get("inicio", 0)): s for s in sesiones_historial}
    segundos = 0.0
    for inicio in {r.get("sesion", 0) for r in registros}:
        s = por_inicio.get(round(inicio))
        if s:
            segundos += max(0.0, s.get("fin", inicio) - s.get("inicio", inicio))
        else:
            fotos = [r["fecha"] for r in registros if r.get("sesion") == inicio]
            segundos += max(fotos) - inicio if fotos else 0
    return segundos / 3600


def totales_objetos(registros: list[dict]) -> dict[str, int]:
    """Suma por objeto (id del catalogo -> cantidad total), de mayor a menor."""
    total: dict[str, int] = {}
    for r in registros:
        for oid, cantidad in (r.get("objetos") or {}).items():
            total[oid] = total.get(oid, 0) + int(cantidad)
    return dict(sorted(total.items(), key=lambda kv: -kv[1]))


def total_oro(registros: list[dict]) -> int:
    return sum(int(r.get("oro") or 0) for r in registros)


def vincular_premios() -> int:
    """Une cada objeto del botin con su objeto de las tablas de premios (lumen/datos/premios.yaml), buscando
    su icono solo entre lo que puede salir en los contenidos donde aparecio. Asi se corrigen los vinculos
    de la galeria que se confunden de color (el botin de los perros de Floor 1-3 tomo "Brokkr's Strength",
    gema roja, por "Eitri's Meticulousness", gema amarilla) y toman nombre los que no estan en la galeria
    (el cubo gris = Esencia magica negra; la caja de regalo de Indura). Devuelve cuantos cambio."""
    catalogo = botin.cargar_catalogo()
    contenidos: dict[str, set[str]] = {}
    for r in _leer_indice():
        for oid in r.get("objetos") or {}:
            contenidos.setdefault(botin.destino(oid, catalogo) or oid, set()).add(r.get("modo", ""))
    galeria = botin.cargar_galeria()
    de_galeria = {premios.info(o).get("galeria"): o for o in premios.todos()}
    de_galeria.pop(None, None)
    cambios = 0
    for oid in botin.visibles(catalogo):
        candidatos = set().union(*(premios.objetos_de(m) for m in contenidos.get(oid, ())))
        img = leer_imagen(botin.ruta_icono(oid)) if candidatos else None
        objeto = botin.en_premios(img, candidatos) if img is not None else None
        datos = catalogo[oid]
        # Si no sale en la tabla de donde aparecio (la tela de Indura viene de su caja de materiales), vale
        # su vinculo con la galeria para saber cual es.
        objeto = objeto or de_galeria.get(datos.get("galeria"))
        if not objeto:
            continue
        antes = dict(datos)
        datos["premio"] = objeto
        info = premios.info(objeto)
        gid = info.get("galeria")
        if gid and gid != datos.get("galeria") and gid in galeria:
            viejo = galeria.get(datos.get("galeria")) or {}
            for campo in ("tipo", "descripcion"):  # lo de la galeria mala fuera; lo escrito a mano se queda
                if not datos.get(campo) or datos.get(campo) == viejo.get(campo):
                    datos[campo] = galeria[gid].get(campo) or ""
            if datos.get("nombre") == viejo.get("nombre"):
                datos["nombre"] = ""
            datos["galeria"] = gid
        # Nombre y descripcion en espanol de la tabla, salvo lo que escribio el jugador (distinto del ingles
        # de la galeria).
        ingles = galeria.get(datos.get("galeria")) or {}
        for campo in ("nombre", "descripcion"):
            if info.get(campo) and (not datos.get(campo) or datos[campo] == ingles.get(campo)):
                datos[campo] = info[campo]
        cambios += datos != antes
    if cambios:
        botin.guardar_catalogo(catalogo)
    return cambios

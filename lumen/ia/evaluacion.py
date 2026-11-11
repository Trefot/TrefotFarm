"""Evaluacion de diarios: importar es lectura, nunca entrenamiento ni ejecucion."""

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from lumen import admin
from lumen.ia import aprendizaje, perfiles

MAX_BYTES = 10 * 1024 * 1024
MAX_REGISTROS = 10000


def leer_archivo(ruta: Path) -> tuple[list[dict], int]:
    admin.exigir()
    with Path(ruta).open("rb") as archivo:
        datos = archivo.read(MAX_BYTES + 1)
    if len(datos) > MAX_BYTES:
        raise ValueError("El diario supera 10 MiB. Exporta una parte más pequeña.")
    salida, invalidos = [], 0
    for linea in datos.decode("utf-8-sig").splitlines():
        if not linea.strip():
            continue
        if len(salida) + invalidos >= MAX_REGISTROS:
            raise ValueError("El diario supera 10.000 registros.")
        try:
            registro = json.loads(linea)
            if not isinstance(registro, dict):
                raise ValueError("registro no valido")
            salida.append(registro)
        except (ValueError, RecursionError):
            invalidos += 1
    return salida, invalidos


def intervalo(victorias: int, total: int) -> tuple[float, float]:
    if not total:
        return 0.0, 1.0
    z = 1.96
    p = victorias / total
    denom = 1 + z * z / total
    centro = (p + z * z / (2 * total)) / denom
    margen = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return max(0.0, centro - margen), min(1.0, centro + margen)


def analizar(registros: list[dict], destino: str, equipo) -> dict:
    admin.exigir()
    heroes = perfiles.equipo_clave(equipo)
    if not heroes:
        raise ValueError("Indica el equipo completo para evaluar partidas comparables.")
    grupos = defaultdict(list)
    problemas = Counter()
    fases = Counter()
    seleccionadas = 0
    for p in registros:
        if (
            not isinstance(p, dict)
            or perfiles.equipo_clave(p.get("equipo")) != heroes
            or (p.get("lecciones") or p.get("destino")) != destino
        ):
            continue
        seleccionadas += 1
        duracion = p.get("duracion")
        if (
            not isinstance(duracion, (int, float))
            or isinstance(duracion, bool)
            or not math.isfinite(duracion)
            or duracion <= 0
        ):
            problemas["duracion_invalida"] += 1
            continue
        resultado = p.get("resultado")
        if resultado not in ("victoria", "derrota", "reinicio"):
            problemas["sin_resultado_comparable"] += 1
            continue
        turnos = p.get("turnos")
        if not isinstance(turnos, list):
            problemas["turnos_invalidos"] += 1
            continue
        confirmadas = sum(
            isinstance(t, dict) and t.get("confirmada") is True for t in turnos
        )
        fallidas = sum(
            isinstance(t, dict) and t.get("confirmada") is False for t in turnos
        )
        problemas["intentos_sin_confirmar"] += fallidas
        if not confirmadas:
            problemas["sin_acciones_confirmadas"] += 1
        if p.get("conocimiento") != perfiles.firma_conocimiento():
            problemas["conocimiento_distinto_o_desconocido"] += 1
        if p.get("calidad", "fiable") != "fiable":
            problemas["calidad_incierta"] += 1
        if resultado != "victoria":
            fases[str(p.get("fase_final") or "?")] += 1
        origen = p.get("origen")
        if origen not in ("juego", "simulacion"):
            origen = "sin_declarar"
        if origen != "juego":
            problemas["origen_no_declarado_como_juego"] += 1
        confiable = (
            confirmadas > 0
            and p.get("conocimiento") == perfiles.firma_conocimiento()
            and p.get("calidad", "fiable") == "fiable"
        )
        config = p.get("config")
        politica = (
            aprendizaje.clave(config)
            if aprendizaje.valida(config)
            else "sin_configuracion"
        )
        # Separar versiones y procedencia: no mezclar demos con partidas ni comparar versiones a ciegas.
        llave = (
            str(p.get("version") or "sin_version")[:80],
            origen,
            politica,
            confiable,
        )
        grupos[llave].append((resultado, duracion))
    medidas = []
    for (version, origen, politica, fiable), filas in sorted(grupos.items()):
        victorias = sum(r == "victoria" for r, _ in filas)
        segundos = sum(t for _, t in filas)
        medidas.append(
            dict(
                version=version,
                origen=origen,
                politica=politica,
                fiable=fiable,
                peleas=len(filas),
                victorias=victorias,
                tasa=victorias / len(filas),
                intervalo=intervalo(victorias, len(filas)),
                por_hora=3600 * victorias / segundos,
            )
        )
    return dict(
        destino=destino,
        equipo=list(heroes),
        seleccionadas=seleccionadas,
        grupos=medidas,
        problemas=dict(problemas),
        fallos_por_fase=dict(fases),
    )


def texto(informe: dict) -> str:
    lineas = [
        f"Evaluación: {informe['destino']}",
        f"Equipo: {', '.join(informe['equipo'])}",
        f"Registros del contexto: {informe['seleccionadas']}",
        "Las cifras describen el diario; el origen es declarado, no una certificación de juego real.",
    ]
    for g in informe["grupos"]:
        bajo, alto = g["intervalo"]
        politica = (
            "sin configuración"
            if g["politica"] == "sin_configuracion"
            else aprendizaje.diferencia(json.loads(g["politica"])) or "base"
        )
        lineas += [
            "",
            f"{g['version']} · {g['origen']} · {politica}",
            f"{g['victorias']}/{g['peleas']} victorias · {g['por_hora']:.1f}/h · tasa {100 * g['tasa']:.1f}%",
            f"Intervalo orientativo 95%: {100 * bajo:.1f}–{100 * alto:.1f}% · calidad {'con evidencia' if g['fiable'] else 'insuficiente'}",
        ]
    if informe["problemas"]:
        lineas += [
            "",
            "Incidencias:",
            *(f"{k}: {v}" for k, v in informe["problemas"].items() if v),
        ]
    if informe["fallos_por_fase"]:
        lineas += [
            "",
            "Derrotas/reinicios por fase:",
            *(f"F{k}: {v}" for k, v in informe["fallos_por_fase"].items()),
        ]
    lineas += [
        "",
        "Prioridad: corregir lecturas y acciones sin confirmar antes de ajustar pesos. Pocas partidas no prueban una mejora.",
    ]
    return "\n".join(lineas)

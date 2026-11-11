"""Ordenar equipos registrados sin crear ni ejecutar equipos nuevos en el juego."""

import math
import re

import lumen
from lumen import admin
from lumen.ia import perfiles, evaluacion


def _modo(destino):
    if re.search(r"_f[123]$", destino):
        return destino.rsplit("_f", 1)[0] + "_pisos1a3"
    return re.sub(r"_(chaos|hell|extreme|hard|normal)$", "", destino)


def recomendar(
    destino: str, biblioteca: dict, catalogo: dict, registros: list[dict]
) -> list[dict]:
    admin.exigir()
    from lumen.modos import MODOS, TODOS_LOS_MODOS

    modo = _modo(destino)
    clase = TODOS_LOS_MODOS.get(modo)
    fijo = getattr(clase, "equipo", None)
    opciones = catalogo.get(modo)
    if opciones is None:
        base = modo.replace("_pisos1a3", "").replace("_piso4", "")
        opciones = catalogo.get(base, [])
    salida = []
    for candidato in opciones or []:
        if not isinstance(candidato, dict):
            continue
        heroes = candidato.get("personajes") or []
        if not perfiles.equipo_clave(heroes):
            continue
        faltan = [h for h in heroes if h not in biblioteca or not biblioteca[h].tengo]
        registrado = bool(candidato.get("bot"))
        compatible = (
            modo in MODOS
            and registrado
            and (fijo is None or list(heroes) == list(fijo.orden))
        )
        comparables = []
        for pelea in registros:
            if not isinstance(pelea, dict):
                continue
            duracion = pelea.get("duracion")
            turnos = pelea.get("turnos")
            if not isinstance(turnos, list):
                continue
            if (
                perfiles.equipo_clave(pelea.get("equipo"))
                == perfiles.equipo_clave(heroes)
                and (pelea.get("lecciones") or pelea.get("destino")) == destino
                and pelea.get("conocimiento") == perfiles.firma_conocimiento()
                and pelea.get("origen") == "juego"
                and pelea.get("version") == lumen.__version__
                and pelea.get("calidad", "fiable") == "fiable"
                and pelea.get("resultado") in ("victoria", "derrota", "reinicio")
                and isinstance(duracion, (int, float))
                and not isinstance(duracion, bool)
                and math.isfinite(duracion)
                and duracion > 0
                and any(
                    isinstance(t, dict) and t.get("confirmada") is True for t in turnos
                )
            ):
                comparables.append(pelea)
        victorias = sum(p["resultado"] == "victoria" for p in comparables)
        segundos = sum(p["duracion"] for p in comparables)
        medidas = len(comparables) >= 5
        salida.append(
            dict(
                nombre=candidato.get("nombre", "Equipo registrado"),
                personajes=heroes,
                faltan=faltan,
                disponible=not faltan,
                compatible=compatible,
                peleas=len(comparables),
                medido=medidas,
                tasa=victorias / len(comparables) if comparables else None,
                limite_inferior=evaluacion.intervalo(victorias, len(comparables))[0]
                if medidas
                else 0,
                por_hora=3600 * victorias / segundos if segundos else None,
                minutos_publicados=candidato.get("minutos"),
                notas=candidato.get("notas", ""),
            )
        )
    return sorted(
        salida,
        key=lambda d: (
            not d["disponible"],
            not d["compatible"],
            not d["medido"],
            -d["limite_inferior"],
            -(d["por_hora"] or 0),
            d["nombre"],
        ),
    )


def texto(destino, recomendaciones):
    lineas = [
        f"Equipos registrados · {destino}",
        "Se consideran tus héroes marcados, compatibilidad declarada y partidas comparables de esta versión.",
        "No modifica el equipo del juego ni inicia pruebas automáticamente.",
    ]
    if not recomendaciones:
        lineas.append("No hay equipos registrados para este contenido.")
    for i, r in enumerate(recomendaciones, 1):
        lineas += [
            "",
            f"{i}. {r['nombre']}",
            ", ".join(r["personajes"]),
            "Disponible" if r["disponible"] else "Faltan: " + ", ".join(r["faltan"]),
            "Compatible con el bot según catálogo"
            if r["compatible"]
            else "Compatibilidad automática no confirmada",
        ]
        if r["medido"]:
            lineas.append(
                f"{r['peleas']} partidas · {100 * r['tasa']:.1f}% victorias · {r['por_hora']:.1f}/h"
            )
        else:
            lineas.append(
                f"Muestra insuficiente: {r['peleas']} partidas comparables; requiere al menos 5."
            )
        if r["minutos_publicados"]:
            lineas.append(
                f"Referencia publicada: {r['minutos_publicados']} min/victoria (no es una medición de esta cuenta)."
            )
        if r["notas"]:
            lineas.append(r["notas"])
    lineas += [
        "",
        "Confirma reliquias, enlaces, equipo y estadísticas indicados en las notas antes de jugar.",
    ]
    return "\n".join(lineas)

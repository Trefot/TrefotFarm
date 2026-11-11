"""Inventario verificable del conocimiento incluido; no inventa reglas ausentes."""

from collections import Counter
import yaml

from lumen import admin
from lumen.rutas import RAIZ
from lumen.ia import decidir


def informe() -> str:
    admin.exigir()
    datos = RAIZ / "lumen" / "datos"

    def leer(nombre):
        ruta = datos / nombre
        return yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}

    personajes = leer("personajes.yaml")
    fichas = leer("fichas.yaml")
    habilidades = leer("habilidades.yaml")
    jefes = leer("jefes.yaml")
    campos = Counter()
    for ficha in fichas.values():
        for campo in ("pasiva", "reliquia", "talento"):
            if (ficha.get(campo) or {}).get("texto"):
                campos[campo] += 1
    lineas = [
        "Conocimiento local de 7DS",
        f"Personajes: {len(personajes)} · fichas: {len(fichas)} · habilidades: {len(habilidades)}",
        f"Textos de pasivas: {campos['pasiva']} · reliquias: {campos['reliquia']} · talentos: {campos['talento']}",
        "Textos disponibles no equivalen a efectos completamente entendidos ni a condiciones observadas en pantalla.",
        "",
        "Destinos y fases con textos de jefe:",
    ]
    for destino, jefe in sorted(jefes.items()):
        fases = (jefe or {}).get("fases") or {}
        detalles = [
            f"F{f}: {len(decidir.mecanicas_de(destino, int(f)))} mecánicas reconocidas"
            for f in fases
        ]
        lineas.append(f"{destino}: " + "; ".join(detalles))
    from lumen.modos import TODOS_LOS_MODOS, CERRADOS

    lineas += ["", "Sin ficha de jefe por fases (puede haber guiones específicos):"]
    for destino in TODOS_LOS_MODOS:
        claves = (
            [destino.replace("_pisos1a3", f"_f{n}") for n in (1, 2, 3)]
            if destino.endswith("_pisos1a3")
            else [destino]
        )
        faltan = [d for d in claves if d not in jefes]
        if faltan:
            lineas.append(
                ", ".join(faltan) + (" · cerrado" if destino in CERRADOS else "")
            )
    lineas += [
        "",
        "Límites: daño relativo, no simulación completa; buffs/vida/orbes no se observan todos. Un guion no prueba conocimiento general.",
    ]
    return "\n".join(lineas)

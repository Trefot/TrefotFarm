"""Relaciona requisitos del jefe con efectos de cartas, sin dar por observados estados desconocidos."""

from dataclasses import dataclass
from collections import Counter
from lumen.cartas import Carta, Rango, TipoCarta
from lumen.ia import decidir


@dataclass(frozen=True)
class Eleccion:
    indice: int
    motivo: str


def satisface(efectos, necesidad):
    dano = next((i for i, e in enumerate(efectos) if e.tipo == "dano"), None)
    if necesidad == "limpiar":
        return any(e.tipo == "limpiar" and e.objetivo == "aliados" for e in efectos)
    if necesidad == "quitar_postura":
        return any(
            e.tipo == "quitar_postura" and e.objetivo in ("uno", "todos")
            for e in efectos
        )
    if necesidad == "evasion":
        return dano is not None and (
            any(e.tipo == "ignora_evasion" for e in efectos)
            or any(
                e.tipo == "quitar_buffs" and e.objetivo in ("uno", "todos")
                for e in efectos[:dano]
            )
        )
    if necesidad == "amplify_power_strike":
        return dano is not None and any(
            e.tipo == "dano_extra" and e.detalle in ("amplify", "power strike")
            for e in efectos
        )
    return False


def opciones(mano, lector, necesidad):
    return [
        i
        for i, carta in enumerate(mano)
        if carta.jugable and satisface(lector.efectos_carta(carta), necesidad)
    ]


def por_estado(destino, fase, mano, observacion, lector):
    """Solo contramedidas con observacion positiva en contextos ya calibrados."""
    contextos = {
        ("pajaro_piso4", 1): ("bloqueo", "limpiar", "limpia el bloqueo de aliados"),
        ("pajaro_piso4", 3): (
            "inmortalidad",
            "amplify_power_strike",
            "Amplify/Power Strike contra la inmortalidad",
        ),
        ("pajaro_piso4", 4): (
            "evasion",
            "evasion",
            "resuelve la evasión antes de atacar",
        ),
    }
    regla = contextos.get((destino, fase))
    if not regla:
        return None
    senal, necesidad, motivo = regla
    confianza = ((observacion or {}).get("senales", {}).get(senal) or {}).get(
        "confianza", 0
    )
    if (
        isinstance(confianza, bool)
        or not isinstance(confianza, (int, float))
        or not 0.90 <= confianza <= 1
    ):
        return None
    disponibles = opciones(mano, lector, necesidad)
    if not disponibles:
        return None
    # Resolver con el menor rango evita gastar una ulti si una normal sirve.
    indice = min(
        disponibles,
        key=lambda i: (mano[i].tipo == TipoCarta.ULTI, mano[i].rango.value, i),
    )
    return Eleccion(
        indice, f"Mecánica observada: {motivo} · rango de la carta verificado"
    )


def requisito_rango(destino, fase):
    for m in decidir.mecanicas_de(destino, fase):
        if m.tipo == "mismo_rango":
            partes = m.detalle.split(":")
            if len(partes) == 2 and all(p.isdigit() for p in partes):
                cantidad, minimo = map(int, partes)
                if 1 <= cantidad <= 4 and 1 <= minimo <= 3:
                    return cantidad, minimo
    return None


def grupo_de_rango(mano, jugadas, restantes, requisito):
    """Rango normal comun que completa el requisito del texto, si la mano lo permite."""
    cantidad, minimo = requisito
    usados = Counter(c.rango for c in jugadas if c.tipo != TipoCarta.ULTI)
    candidatos = []
    for rango in (Rango.BRONCE, Rango.PLATA, Rango.ORO):
        if rango.value + 1 < minimo:
            continue
        indices = [
            i
            for i, c in enumerate(mano)
            if c.jugable and c.tipo != TipoCarta.ULTI and c.rango == rango
        ]
        if usados[rango] + min(len(indices), restantes) >= cantidad:
            candidatos.append((rango, indices, usados[rango]))
    return min(candidatos, key=lambda x: (-x[2], x[0].value)) if candidatos else None


def informe_equipo(destino, equipo, lector=None):
    lector = lector or decidir.LectorCartas()
    if not equipo:
        return (
            "Indica los personajes del equipo para contrastar sus cartas con el jefe."
        )
    lineas = [
        f"Capacidades por efectos · {destino}",
        "No simula una victoria ni comprueba equipo, reliquias, vida u orbes en pantalla.",
    ]
    cartas = []
    for pid in equipo:
        pj = lector.biblioteca.get(pid)
        if not pj:
            lineas.append(f"Sin ficha: {pid}")
            continue
        for cid in pj.cartas:
            for rango in (
                (Rango.ULTI,)
                if cid == "ulti"
                else (Rango.BRONCE, Rango.PLATA, Rango.ORO)
            ):
                cartas.append(
                    Carta(
                        nombre=f"{pid}.{cid}",
                        rango=rango,
                        tipo=TipoCarta.ULTI if cid == "ulti" else TipoCarta.NORMAL,
                    )
                )
    fases = (decidir._jefes().get(destino) or {}).get("fases") or {}
    if not fases:
        lineas.append(
            "Sin texto de jefe por fases para este destino: no se supone compatibilidad."
        )
    for fase in fases:
        lineas.append(f"\nFase {fase}:")
        for m in decidir.mecanicas_de(destino, int(fase)):
            necesidad = {
                "evasion": "evasion",
                "bloqueo": "limpiar",
                "postura": "quitar_postura",
            }.get(m.tipo)
            if (
                destino == "pajaro_piso4"
                and int(fase) == 3
                and m.tipo == "inmortalidad"
            ):
                necesidad = "amplify_power_strike"
            if necesidad:
                candidatas = opciones(cartas, lector, necesidad)
                nombres = sorted(
                    {
                        f"{cartas[i].nombre} ({cartas[i].rango.name.lower()})"
                        for i in candidatas
                    }
                )
                lineas.append(
                    f"- {m.tipo}: "
                    + (
                        ", ".join(nombres)
                        if nombres
                        else "sin carta documentada que la resuelva directamente"
                    )
                )
            elif m.tipo == "mismo_rango":
                lineas.append(
                    f"- Requiere mismo rango: {m.detalle} (cantidad:rango mínimo); depende de la mano y las fusiones."
                )
            else:
                lineas.append(
                    f"- {m.tipo}: regla descrita; su ejecución requiere contexto/guion validado."
                )
    lineas.append(
        "\nUn efecto que solo aparece en oro no se atribuye a una carta de bronce. Las condiciones de pasivas y reliquias no se dan por cumplidas."
    )
    return "\n".join(lineas)


def resumen_requisitos(destino):
    datos = decidir._jefes().get(destino) or {}
    fases = datos.get("fases") or {}
    if not fases:
        return "Sin ficha de mecánicas por fases para este destino. No se supone compatibilidad de cualquier equipo."
    etiquetas = {
        "inmortalidad": "resolver la inmortalidad según la fase",
        "evasion": "ignorar o retirar la evasión antes del daño",
        "bloqueo": "limpiar el bloqueo si aparece",
        "postura": "cancelar posturas cuando estén presentes",
        "torrent": "gestionar Torrent con las ultis",
        "reduccion_dano_atributo": "seguir el atributo requerido por la fase",
        "defensa_atributo": "seguir la secuencia y el estado de la fase",
    }
    lineas = ["Mecánicas documentadas (no comprueba el equipo puesto):"]
    for fase in fases:
        partes = []
        for m in decidir.mecanicas_de(destino, int(fase)):
            if m.tipo == "mismo_rango":
                requisito = requisito_rango(destino, int(fase))
                if requisito:
                    partes.append(
                        f"{requisito[0]} habilidades del mismo rango ({requisito[1]} o superior)"
                    )
            elif (
                destino == "pajaro_piso4"
                and int(fase) == 3
                and m.tipo == "inmortalidad"
            ):
                partes.append("resolver la inmortalidad con Amplify/Power Strike")
            elif m.tipo in etiquetas:
                partes.append(etiquetas[m.tipo])
        if partes:
            lineas.append(f"F{fase}: " + "; ".join(dict.fromkeys(partes)) + ".")
    if len(lineas) == 1:
        lineas.append(
            "Hay textos de jefe, pero faltan reglas ejecutables para resumirlos."
        )
    return "\n".join(lineas)

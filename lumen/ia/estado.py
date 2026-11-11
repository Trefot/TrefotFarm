"""Observaciones positivas de iconos conocidos. Ausencia de coincidencia = desconocido."""

import numpy as np

from lumen import juego
from lumen.ia.efectos import Mecanica

UMBRAL = 0.90


def observar(pantalla) -> dict:
    senales = {}
    if (
        isinstance(pantalla, np.ndarray)
        and pantalla.ndim == 3
        and pantalla.shape[0] >= 650
    ):
        # Excluir cartas y menus inferiores para reducir coincidencias con dibujos de habilidades.
        zona = pantalla[100:650]
        for nombre, plantilla in (
            ("evasion", juego.evasion),
            ("inmortalidad", juego.inmortalidad),
            ("bloqueo", juego.bloqueo_habilidades),
        ):
            valor, rect = plantilla.confianza(zona)
            if valor >= UMBRAL:
                x, y, w, h = map(int, rect)
                senales[nombre] = {
                    "confianza": float(valor),
                    "rect": [x, y + 100, w, h],
                }
    return {"senales": senales, "vida": None, "orbes": None, "postura": None}


def mecanicas(observacion, destino="", fase=None) -> list:
    # Los iconos no identifican por si solos al afectado. Limitar ajustes a los
    # contextos ya contemplados por el guion del pajaro; el resto solo se registra.
    contras = {"inmortalidad": ()}
    if destino == "pajaro_piso4" and fase == 4:
        contras["evasion"] = ("ignora_evasion", "ulti")
    if destino == "pajaro_piso4" and fase == 1:
        contras["bloqueo"] = ("limpiar",)
    salida = []
    for nombre, datos in observacion.get("senales", {}).items():
        valor = datos.get("confianza", 0) if isinstance(datos, dict) else 0
        if (
            nombre in contras
            and isinstance(valor, (int, float))
            and not isinstance(valor, bool)
            and UMBRAL <= valor <= 1
        ):
            salida.append(Mecanica(nombre, contras[nombre]))
    return salida


def texto(observacion) -> str:
    partes = [
        f"{nombre}: icono visible ({datos['confianza']:.2f})"
        for nombre, datos in observacion.get("senales", {}).items()
    ]
    return "\n".join(
        partes
        + [
            "Vida, orbes y postura: sin lectura calibrada.",
            "Un icono sin coincidencia se trata como desconocido, no como ausente.",
            "Los ajustes por icono se limitan a los contextos conocidos del pájaro F4; otros se registran sin deducir contramedidas.",
        ]
    )

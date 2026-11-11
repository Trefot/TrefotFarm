"""Analisis de capturas guardadas. No captura ventanas, ejecuta entradas ni escribe diarios.

Cada imagen se analiza por separado con la IA general; no reproduce guiones ni
supone que una accion propuesta llego a ejecutarse entre dos capturas.
"""

from dataclasses import dataclass, field
from pathlib import Path
import re

import cv2
import numpy as np

from lumen import admin, cartas, inteligencia, juego
from lumen.ia import decidir, perfiles
from lumen.vision import leer_imagen


@dataclass
class Resultado:
    imagen: np.ndarray
    mano: list
    paso: tuple | None
    acciones: int
    estado: str
    razones: dict
    destino: str
    fase: int
    manual: bool
    comparacion: dict = field(default_factory=dict)
    observacion: dict = field(default_factory=dict)

    def texto(self) -> str:
        lineas = [
            self.estado,
            f"Contexto: {self.destino or 'general'} · fase {self.fase}",
            f"Acciones: {self.acciones}"
            + (" (indicadas manualmente)" if self.manual else " (detectadas)"),
            "IA general · imagen independiente · sin ejecutar clics",
        ]
        if self.paso is None:
            lineas.append(
                "Sin jugada propuesta: no se detecta turno o no hay cartas jugables."
            )
        elif self.paso[0] == "jugar":
            lineas.append(f"Propuesta: jugar carta {self.paso[1] + 1}.")
        else:
            lineas.append(
                f"Propuesta: mover carta {self.paso[1] + 1} sobre {self.paso[2] + 1}."
            )
        lineas += ["", "Mano reconocida:", *(str(c) for c in self.mano)]
        if self.razones:
            lineas += [
                "",
                "Ajustes de valor:",
                *(
                    f"{nombre}: {', '.join(motivos)}"
                    for nombre, motivos in self.razones.items()
                ),
            ]
        if self.comparacion:
            c = self.comparacion
            lineas += [
                "",
                "Comparación con la misma mano:",
                f"Base: {_texto_paso(c['base'])}",
                f"Aprendida: {_texto_paso(c['aprendida'])}",
                f"Equipo: {', '.join(c['equipo']) or 'sin identificar; no se aplica memoria'}",
                f"Partidas comparables: {c['peleas']}",
                "Una propuesta distinta no demuestra que gane más.",
            ]
        if self.observacion:
            from lumen.ia import estado
            lineas += ["", "Estado observado:", estado.texto(self.observacion)]
        return "\n".join(lineas)


def _texto_paso(paso):
    if paso is None:
        return "sin jugada"
    if paso[0] == "jugar":
        return f"jugar carta {paso[1] + 1}"
    return f"mover carta {paso[1] + 1} sobre {paso[2] + 1}"


def ordenar(rutas) -> list[Path]:
    """Orden natural: captura2 antes que captura10, sin duplicados."""
    return sorted(
        dict.fromkeys(Path(r) for r in rutas),
        key=lambda p: [
            int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(p).lower())
        ],
    )


@perfiles.lectura
def analizar(
    ruta: Path,
    *,
    demonio: bool = False,
    acciones: int = 0,
    destino: str = "",
    fase: int = 1,
    equipo=None,
) -> Resultado:
    admin.exigir()
    from lumen.control import control

    if control.ejecutando:
        raise RuntimeError("Deten el bot antes de comparar capturas.")
    if not 0 <= acciones <= 6 or not 1 <= fase <= 4:
        raise ValueError("Indica de 0 a 6 acciones y una fase de 1 a 4.")
    imagen = leer_imagen(Path(ruta))
    if imagen is None:
        raise ValueError("No se pudo leer esta imagen.")
    if imagen.shape[:2] != (940, 550):
        raise ValueError(
            "Abre una captura de la ventana del juego de 550 × 940 px; una captura de escritorio necesita recortarse primero."
        )
    estado = "Pantalla sin clasificar"
    final = False
    for nombre, plantilla in (("Victoria", juego.victoria), ("Derrota", juego.derrota)):
        valor, _ = plantilla.confianza(imagen)
        if valor >= 0.8:
            estado, final = f"{nombre} · coincidencia {valor:.2f}", True
            break
    if not final:
        fases = [
            (n, p.confianza(imagen)[0])
            for n, p in (
                (1, juego.fase_1),
                (2, juego.fase_2),
                (3, juego.fase_3),
                (4, juego.fase_4),
            )
        ]
        numero, valor = max(fases, key=lambda x: x[1])
        if valor >= 0.8:
            estado = f"Indicador de fase {numero} · coincidencia {valor:.2f} (contexto elegido: fase {fase})"
    mano = cartas.leer_mano_demonio(imagen) if demonio else cartas.leer_mano(imagen)
    detectadas = (
        cartas.casillas_libres_demonio(imagen)
        if demonio
        else cartas.contar_huecos(imagen)
    )
    cantidad = min(6 if demonio else 4, acciones or detectadas)
    from lumen.ia import diario

    equipo = perfiles.equipo_clave(equipo)
    jugador = inteligencia.Jugador(arrastrar=not demonio)
    from lumen.ia import estado as estado_ia
    observacion = estado_ia.observar(imagen)
    jugador.observacion = observacion
    jugador.equipo = equipo
    jugador.usar_aprendizaje = False
    jugador.destino, jugador.fase = destino, fase
    jugador.mecanicas = decidir.mecanicas_de(destino, fase)
    # Cargar y reconocer tambien sin turno: sirve para inspeccionar el lector de cartas.
    jugador._cargar()
    inteligencia.agrupar_por_dibujo(mano, jugador._identificar)
    base = jugador.elegir(mano, cantidad) if cantidad and not final else None
    origen_diario = (
        destino.rsplit("_f", 1)[0] + "_pisos1a3"
        if re.search(r"_f[123]$", destino)
        else destino
    )
    if demonio:
        origen_diario = re.sub(r"_(chaos|hell|extreme|hard|normal)$", "", destino)
    historia = perfiles.filtrar(diario.leer(origen_diario, 1000), destino, equipo)
    jugador.params = perfiles.parametros(destino, equipo, historia)
    jugador.usar_aprendizaje = True
    jugador._acciones_antes = 0
    jugador.jugadas_turno = []
    paso = jugador.elegir(mano, cantidad) if cantidad and not final else None
    comparacion = {
        "base": base,
        "aprendida": paso,
        "equipo": list(equipo),
        "peleas": len(historia),
        "parametros": jugador.params,
    }
    admin.exigir()  # una sesion revocada durante el calculo no entrega resultados
    return Resultado(
        imagen,
        mano,
        paso,
        cantidad,
        estado,
        jugador.razones,
        destino,
        fase,
        bool(acciones),
        comparacion,
        observacion,
    )


def anotar(resultado: Resultado) -> np.ndarray:
    imagen = resultado.imagen.copy()
    seleccion = set(resultado.paso[1:]) if resultado.paso else set()
    for c in resultado.mano:
        x, y, w, h = c.rect
        color = (
            (70, 210, 255)
            if c.posicion in seleccion
            else (110, 200, 110)
            if c.jugable
            else (90, 90, 220)
        )
        cv2.rectangle(imagen, (x, y), (x + w, y + h), color, 2)
        cv2.putText(
            imagen,
            str(c.posicion + 1),
            (x + 3, y + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
        )
    if resultado.paso:
        centros = {
            c.posicion: (c.rect[0] + c.rect[2] // 2, c.rect[1] + c.rect[3] // 2)
            for c in resultado.mano
        }
        if resultado.paso[0] == "mover":
            cv2.arrowedLine(
                imagen,
                centros[resultado.paso[1]],
                centros[resultado.paso[2]],
                (70, 210, 255),
                3,
            )
        else:
            cv2.circle(imagen, centros[resultado.paso[1]], 14, (70, 210, 255), 3)
    return imagen

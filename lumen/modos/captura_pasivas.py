"""Captura de gracias, pasivas y reliquias (solo administrador), para que la IA sepa lo que hace cada heroe.

Recorre las fichas como la captura de artworks (desde la ficha de un heroe, flecha a la derecha, termina al
volver al primero). En cada ficha toca los iconos de la fila "Grace / Unique": la Gracia, la pasiva unica
(Unique) y la Reliquia (Holy Relic), y algun otro si lo hay. De cada ventana lee el nombre y el texto, la
cierra con la X y sigue. Medido con Covenant of Light Ludociel (capturas del 2026-10-29).

Se guarda en capturas/heroes/catalogo.yaml, en cada heroe: ``gracia`` y ``pasiva`` ({nombre, texto}),
``reliquias`` ([{nombre, efecto}]) y ``otras`` (ventanas con otro titulo).
"""

import re
import time

import cv2
import numpy as np

from lumen import entrada, ocr
from lumen.modos import captura_heroes as C
from lumen.modos.captura_artworks import CapturaArtworks
from lumen.vision import Plantilla, guardar_imagen

CERRAR = Plantilla("heroes/cerrar_ventana.png")  # la X roja de las ventanas de Gracia, Unique y Reliquia
# Iconos de la fila "Grace / Unique" (ficha de 550x940): Gracia, Unique, Reliquia y un hueco mas por si acaso
ICONOS = ((80, 785), (157, 785), (240, 785), (320, 785))
COLUMNAS_TEXTO = (70, 480)
ESPERA_VENTANA = 2.5  # sin ventana tras tocar un icono: ese hueco esta vacio y no hay mas


def zona_texto(pantalla) -> tuple[int, int] | None:
    """Filas de la banda gris oscura donde va el texto de la ventana (y1, y2)."""
    hsv = cv2.cvtColor(pantalla[:, 120:430], cv2.COLOR_BGR2HSV)
    gris = ((hsv[..., 1] < 60) & (hsv[..., 2] > 60) & (hsv[..., 2] < 120)).mean(1)
    filas = np.where(gris > 0.5)[0]
    if filas.size < 40:
        return None
    return int(filas.min()), int(filas.max())


def leer_texto(recorte) -> list[str]:
    """Las lineas del texto. Los numeros de color (naranja) a veces se pierden: se lee tal cual y en gris (el
    canal mas claro) y gana la lectura con mas porcentajes ("8%" solo salia en gris)."""
    gris = cv2.cvtColor(recorte.max(2), cv2.COLOR_GRAY2BGR)
    lecturas = [ocr.leer(recorte), ocr.leer(gris, escala=3)]
    return max(lecturas, key=lambda ls: (" ".join(ls).count("%"), len(" ".join(ls))))


def leer_ventana(pantalla, x_cerrar: tuple[int, int, int, int]) -> dict | None:
    """{tipo, titulo, nombre, texto} de la ventana abierta (Gracia, Unique, Reliquia u otra)."""
    banda = zona_texto(pantalla)
    if banda is None:
        return None
    y1, y2 = banda
    x1, x2 = COLUMNAS_TEXTO
    cabecera = [l.strip() for l in ocr.leer(pantalla[max(0, x_cerrar[1] - 10):y1, 60:490]) if len(l.strip()) > 1]
    cuerpo = [l.strip() for l in leer_texto(pantalla[y1:y2, x1:x2]) if l.strip()]
    todo = " ".join(cabecera + cuerpo).lower()
    titulo = cabecera[0] if cabecera else ""
    if "holy relic" in todo:
        tipo = "reliquia"
        nombre = next((l for l in reversed(cabecera) if "holy relic" not in l.lower()), "")
        cuerpo = [l for l in cuerpo if "holy relic effect" not in l.lower()]
    else:
        tipo = "gracia" if titulo.lower().startswith("grac") else "pasiva" if titulo.lower().startswith("uniq") else "otra"
        nombre, cuerpo = (cuerpo[0], cuerpo[1:]) if cuerpo else ("", [])
        nombre = re.sub(r"^\[.*?\]\s*", "", nombre)  # la gracia lleva el titulo del heroe encima
    texto = re.sub(r"\s+", " ", " ".join(cuerpo)).strip()
    return {"tipo": tipo, "titulo": titulo, "nombre": nombre, "texto": texto}


class CapturaPasivas(CapturaArtworks):
    id = "captura_pasivas"
    nombre = "Captura de gracias, pasivas y reliquias"
    descripcion = "Lee la Gracia, la pasiva única y la Reliquia de cada héroe."
    nombres_estados = {"ficha": "Leyendo la ficha", "leer": "Leyendo la ventana", "cerrado": "Cerrando la ventana",
                       "volver": "Volviendo a la ficha"}

    def __init__(self, valores: dict):
        super().__init__(valores)
        self.icono = 0
        self.leidas: list[dict] = []

    def estados(self):
        return {"ficha": self.ficha, "leer": self.leer, "cerrado": self.cerrado, "volver": self.volver}

    def _ya_hecho(self, pid: str) -> bool:
        return bool(self.catalogo.get(pid, {}).get("pasivas_capturadas"))

    def _empezar_heroe(self, p, o):
        self.icono, self.leidas = 0, []
        return self._abrir(o)

    def _abrir(self, o):
        if self.icono >= len(ICONOS):
            return self._guardar_heroe(o)
        entrada.clic(ICONOS[self.icono], o, espera=1.2)
        self.desde = time.time()
        return "leer"

    def leer(self, p, o):
        rect = CERRAR.buscar(p, 0.85)
        if rect is None:
            if time.time() - self.desde > ESPERA_VENTANA:  # hueco vacio: no hay mas iconos
                return self._guardar_heroe(o)
            return None
        ventana = leer_ventana(p, tuple(int(v) for v in rect))
        if ventana and (ventana["nombre"] or ventana["texto"]):
            self.leidas.append(ventana)
            self.log(f"   {ventana['tipo']}: {ventana['nombre']}", "debug")
        else:
            guardar_imagen(C.CARPETA / "sin_leer" / f"pasiva_{time.strftime('%H%M%S')}.jpg", p)
            self.log("No pude leer esta ventana (guardo la captura en capturas/heroes/sin_leer).", "aviso")
        entrada.clic(tuple(int(v) for v in (rect[0] + rect[2] // 2, rect[1] + rect[3] // 2)), o, espera=0.8)
        self.icono += 1
        self.desde = time.time()
        return "cerrado"

    def cerrado(self, p, o):
        rect = CERRAR.buscar(p, 0.85)
        if rect is None and C.FICHA.esta(p, 0.85):
            return self._abrir(o)
        if time.time() - self.desde > 3 and rect is not None:  # la X no cerro: otra vez
            entrada.clic((int(rect[0] + rect[2] // 2), int(rect[1] + rect[3] // 2)), o, espera=0.8)
            self.desde = time.time()
        return None

    def _guardar_heroe(self, o):
        h = self.catalogo[self.actual]
        for v in self.leidas:
            if v["tipo"] == "reliquia":
                reliquias = h.setdefault("reliquias", [])
                if not any(r.get("nombre") == v["nombre"] for r in reliquias):
                    reliquias.append({"nombre": v["nombre"], "efecto": v["texto"]})
            elif v["tipo"] in ("gracia", "pasiva"):
                h[v["tipo"]] = {"nombre": v["nombre"], "texto": v["texto"]}
            else:
                h.setdefault("otras", []).append({"titulo": v["titulo"], "nombre": v["nombre"], "texto": v["texto"]})
        h["pasivas_capturadas"] = time.strftime("%Y-%m-%d %H:%M")
        C.guardar_catalogo(self.catalogo)
        self.hechos += 1
        self._stats()
        tipos = ", ".join(v["tipo"] for v in self.leidas) or "nada"
        self.log(f"{h.get('nombre', self.actual)}: {tipos} ({self.hechos}).", "ok")
        return self._siguiente(o)

    def al_terminar(self):
        self.log(f"Gracias, pasivas y reliquias: {self.hechos} héroes leídos, {self.saltados} saltados.", "ok")

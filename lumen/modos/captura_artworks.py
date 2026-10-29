"""Captura de artworks (solo administrador): la ilustracion de cada heroe, para sus retratos.

Desde la ficha de un heroe (la de Skills, la misma que recorre la Captura de heroes): toca la figura, que
abre su perfil; en el perfil toca "Artwork"; guarda la ilustracion; vuelve atras dos veces y pasa al
siguiente con la flecha de la derecha. Termina al volver al primero.

Cada heroe se reconoce por su nombre y atributo (los de capturas/heroes/catalogo.yaml) y se guarda en su
carpeta de la captura: artwork.jpg (la ilustracion entera) y cara_artwork.jpg (cabeza y hombros, para los
retratos de Personajes, Equipos e Inicio). Al terminar, las caras pasan a la pagina Personajes.
"""

import shutil
import time

import cv2
import numpy as np

from lumen import entrada
from lumen import personajes as P
from lumen.motor import Modo, TerminarModo
from lumen.modos import captura_heroes as C
from lumen.vision import Plantilla, guardar_imagen, leer_imagen

BOTON_ARTWORK = Plantilla("heroes/boton_artwork.png")  # boton "Artwork" del perfil (captura de 2026-10-29)
# Puntos de la figura que abren el perfil (medido en la ficha de Ludociel): si el primero no lo abre (figuras
# pequenas o desplazadas), se prueban los otros.
FIGURA = ((385, 500), (360, 420), (400, 600))
ILUSTRACION = (8, 112, 550, 940)  # x1, y1, x2, y2: sin la barra de arriba (oro, gemas...)
SIN_NOMBRE = 740  # mas abajo va el nombre del heroe (fuera del recorte de la cara)
LADO_CARA = 0.5  # lado de la cara frente al ancho de la ilustracion
DIF_QUIETA = 3.0
ARTWORK = "artwork.jpg"


def recorte_cara(ilustracion: np.ndarray) -> np.ndarray:
    """Cabeza y hombros: un cuadrado centrado en la figura, arriba del todo. La figura se separa del fondo
    (liso) por color; su centro es el de la parte de arriba de la figura (la cabeza, con alas y armas)."""
    alto = min(ilustracion.shape[0], SIN_NOMBRE - ILUSTRACION[1])
    ilu = ilustracion[:alto]
    lab = cv2.cvtColor(ilu, cv2.COLOR_BGR2LAB).astype(np.float32)
    borde = np.concatenate([lab[:15].reshape(-1, 3), lab[:, :10].reshape(-1, 3), lab[:, -10:].reshape(-1, 3)])
    figura = (np.linalg.norm(lab - np.median(borde, 0), axis=2) > 28).astype(np.uint8)
    figura = cv2.morphologyEx(figura, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    ancho = ilu.shape[1]
    lado = int(ancho * LADO_CARA)
    filas = np.where(figura.sum(1) > 8)[0]
    arriba = int(filas[0]) if filas.size else 0
    banda = figura[arriba:arriba + int(lado * 0.6)].sum(0)
    centro = int(np.average(np.arange(ancho), weights=banda)) if banda.sum() else ancho // 2
    x0 = max(0, min(ancho - lado, centro - lado // 2))
    y0 = max(0, min(alto - lado, arriba - 10))
    return ilu[y0:y0 + lado, x0:x0 + lado].copy()


def pasar_caras(catalogo: dict) -> int:
    """Copia cara_artwork.jpg de cada heroe capturado a su personaje (pagina Personajes). Devuelve cuantas."""
    biblioteca = P.cargar()
    base = P._leer_yaml(P.BASE)
    capturados = list(catalogo.values())
    hechas = 0
    for pid_captura, h in catalogo.items():
        cara = C.CARPETA / pid_captura / P.CARA_ARTWORK
        if not cara.is_file():
            continue
        destino = C._existente(h, biblioteca, base, capturados) or pid_captura
        (P.CARPETA / destino).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cara, P.CARPETA / destino / P.CARA_ARTWORK)
        hechas += 1
    return hechas


class CapturaArtworks(Modo):
    id = "captura_artworks"
    nombre = "Captura de artworks"
    descripcion = "Guarda la ilustración (Artwork) de cada héroe para sus retratos."
    guardar_historial = False
    pausa_entre_pasos = 0.4
    nombres_estados = {"ficha": "Leyendo la ficha", "perfil": "Abriendo Artwork", "artwork": "Guardando la ilustración",
                       "volver": "Volviendo a la ficha"}

    def __init__(self, valores: dict):
        super().__init__(valores)
        self.catalogo = C.cargar_catalogo()
        self.primero: str | None = None
        self.actual: str | None = None
        self.anterior_id: str | None = None
        self.hechos = self.saltados = 0
        self.toques = 0
        self.desde = time.time()
        self.previa = None

    def estado_inicial(self):
        return "ficha"

    def estados(self):
        return {"ficha": self.ficha, "perfil": self.perfil, "artwork": self.artwork, "volver": self.volver}

    def _quieta(self, p, zona=ILUSTRACION) -> bool:
        x1, y1, x2, y2 = zona
        actual = cv2.resize(p[y1:y2, x1:x2], (64, 64)).astype(np.int16)
        quieta = self.previa is not None and float(np.abs(actual - self.previa).mean()) < DIF_QUIETA
        self.previa = actual
        return quieta

    def _quien(self, p) -> str | None:
        """El id del heroe de la ficha en la captura de heroes (por [titulo] nombre y atributo)."""
        titulo, nombre = C.leer_cabecera(p)
        if not nombre:
            return None
        clave = f"[{titulo}] {nombre}" if titulo else nombre
        atributo = C.atributo_por_icono(p)
        iguales = [pid for pid, h in self.catalogo.items() if (h or {}).get("clave") == clave]
        if len(iguales) > 1 and atributo:
            iguales = [pid for pid in iguales if self.catalogo[pid].get("atributo") == atributo] or iguales
        if iguales:
            return iguales[0]
        parecida = C.parecida(clave, [h.get("clave", "") for h in self.catalogo.values()], 0.85)
        return next((pid for pid, h in self.catalogo.items() if h.get("clave") == parecida), None) if parecida else None

    def _stats(self):
        self.publicar_stats(victorias=self.hechos, artworks=self.hechos, saltados=self.saltados)

    # ------------------------------------------------------------------ estados
    def ficha(self, p, o):
        if not C.FICHA.esta(p, 0.85):
            if time.time() - self.desde > 30:
                self.log("No veo la ficha de un héroe (la de Skills). Ábrela en el juego y vuelve a empezar.", "error")
                raise TerminarModo()
            return None
        # En la ficha la figura del heroe se mueve todo el rato: se espera solo a que quede quieta la fila de
        # cartas (como la Captura de heroes). Con toda la ilustracion nunca quedaba quieta y no capturaba nada.
        if not self._quieta(p, C.ZONAS_ESTABLES[0]):
            return None
        pid = self._quien(p)
        if pid is None or pid == self.anterior_id:
            if time.time() - self.desde > 12:  # la flecha no paso de heroe, o no se lee el nombre: siguiente
                self.log("No reconozco este héroe (o la flecha no avanzó): paso al siguiente.", "aviso")
                self.saltados += 1
                self._stats()
                return self._siguiente(o)
            return None
        if pid == self.primero:
            self.log(f"Vuelvo al primer héroe: terminado ({self.hechos} artworks).", "ok")
            raise TerminarModo()
        self.primero = self.primero or pid
        self.actual = pid
        if self.valores.get("solo_nuevos", True) and self._ya_hecho(pid):
            self.log(f"{self.catalogo[pid].get('nombre', pid)} ya está capturado: lo salto.", "debug")
            return self._siguiente(o)
        return self._empezar_heroe(p, o)

    # Lo que cambia en otras capturas que recorren las fichas igual (captura_pasivas.py)
    def _ya_hecho(self, pid: str) -> bool:
        return (C.CARPETA / pid / ARTWORK).is_file()

    def _empezar_heroe(self, p, o):
        self.toques = 0
        return self._tocar_figura(o)

    def _tocar_figura(self, o):
        entrada.clic(FIGURA[self.toques % len(FIGURA)], o, espera=1.5)
        self.toques += 1
        self.desde = time.time()
        return "perfil"

    def perfil(self, p, o):
        if self.clic_si(BOTON_ARTWORK, p, o, umbral=0.85, espera=2.0):
            self.desde, self.previa = time.time(), None
            return "artwork"
        if time.time() - self.desde > 3:
            if C.FICHA.esta(p, 0.85) and self.toques < len(FIGURA):
                return self._tocar_figura(o)  # la figura no abrio el perfil: probar en otro punto
            self.log("No se abre el perfil de este héroe: lo salto.", "aviso")
            self.saltados += 1
            self._stats()
            return "volver"
        return None

    def artwork(self, p, o):
        if BOTON_ARTWORK.esta(p, 0.85) or C.FICHA.esta(p, 0.85):  # aun no se abrio
            if time.time() - self.desde > 6:
                self.log("No se abrió el Artwork: lo salto.", "aviso")
                self.saltados += 1
                self._stats()
                return "volver"
            return None
        if not self._quieta(p) and time.time() - self.desde < 8:
            return None
        x1, y1, x2, y2 = ILUSTRACION
        ilustracion = p[y1:y2, x1:x2]
        carpeta = C.CARPETA / self.actual
        guardar_imagen(carpeta / ARTWORK, ilustracion)
        guardar_imagen(carpeta / P.CARA_ARTWORK, recorte_cara(ilustracion))
        self.hechos += 1
        self._stats()
        self.log(f"Artwork de {self.catalogo[self.actual].get('nombre', self.actual)} ({self.hechos}).", "ok")
        entrada.clic(C.VOLVER, o, espera=1.5)
        self.desde = time.time()
        return "volver"

    def volver(self, p, o):
        if C.FICHA.esta(p, 0.85):
            return self._siguiente(o)
        if time.time() - self.desde > 2.5:  # del artwork al perfil y del perfil a la ficha
            entrada.clic(C.VOLVER, o, espera=1.5)
            self.desde = time.time()
        return None

    def _siguiente(self, o):
        self.anterior_id = self.actual
        entrada.clic(C.FLECHA_HEROE, o, espera=1.5)
        self.desde, self.previa = time.time(), None
        return "ficha"

    def al_terminar(self):
        try:
            caras = pasar_caras(self.catalogo)
        except Exception as error:  # el resumen nunca debe romper el final
            self.log(f"No pude pasar las caras a Personajes: {error}", "error")
            caras = 0
        self.log(f"Artworks: {self.hechos} guardados, {self.saltados} saltados; {caras} caras en Personajes.", "ok")

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
from lumen.rutas import ASSETS
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


BORDE_ARRIBA = 20  # sombra de la barra del juego que queda arriba de la ilustracion guardada


def _zona_cara(ilustracion: np.ndarray) -> np.ndarray:
    """La parte de la ilustracion donde se busca la cara: sin la sombra de la barra ni el nombre de abajo."""
    alto = min(ilustracion.shape[0], SIN_NOMBRE - ILUSTRACION[1])
    return ilustracion[BORDE_ARRIBA:alto]


def cara_en(ilustracion: np.ndarray, cx: int, cy: int) -> np.ndarray:
    """El cuadrado de la cara centrado en (cx, cy) de la ilustracion (la cara un poco por encima del centro)."""
    ilu = _zona_cara(ilustracion)
    alto, ancho = ilu.shape[:2]
    lado = int(ancho * LADO_CARA)
    cy -= BORDE_ARRIBA
    x0 = max(0, min(ancho - lado, cx - lado // 2))
    y0 = max(0, min(alto - lado, cy - int(lado * 0.45)))
    return ilu[y0:y0 + lado, x0:x0 + lado].copy()


# Detector de caras de anime: lbpcascade_animeface de nagadomi (licencia MIT, dentro del propio archivo;
# github.com/nagadomi/lbpcascade_animeface). En los primeros 25 artworks encontro la cara de 20.
DETECTOR_CARAS = ASSETS / "modelos" / "lbpcascade_animeface.xml"
_detector = None


def buscar_cara(ilustracion: np.ndarray) -> tuple[int, int] | None:
    """Centro de la cara (la mas grande) en la ilustracion, con el detector de caras de anime; None si no hay."""
    global _detector
    if _detector is None:
        _detector = cv2.CascadeClassifier(str(DETECTOR_CARAS)) if DETECTOR_CARAS.is_file() else False
    if not _detector or _detector.empty():
        return None
    gris = cv2.equalizeHist(cv2.cvtColor(_zona_cara(ilustracion), cv2.COLOR_BGR2GRAY))
    caras = _detector.detectMultiScale(gris, scaleFactor=1.03, minNeighbors=3, minSize=(36, 36))
    if len(caras) == 0:
        return None
    x, y, w, h = max(caras, key=lambda r: r[2] * r[3])
    return int(x + w / 2), int(y + h / 2) + BORDE_ARRIBA


def recorte_cara(ilustracion: np.ndarray) -> np.ndarray:
    """Cabeza y hombros, centrado en la cara que encuentra el detector de caras de anime. Si no la encuentra
    (armaduras, criaturas: Galland, Captain Hawk), se estima como antes: """
    centro = buscar_cara(ilustracion)
    if centro is not None:
        return cara_en(ilustracion, *centro)
    return _cara_estimada(ilustracion)


def _cara_estimada(ilustracion: np.ndarray) -> np.ndarray:
    """Cabeza y hombros. Primero, un cuadrado centrado en lo mas alto de la figura (separada del fondo liso por
    color). Si dentro no hay ninguna mancha de piel grande (la cara), se centra en la mancha de piel mas alta
    de la mitad de arriba: con dragones, alas o destellos arriba (Lillia, Sun God Freyr) salia otra cosa.
    Probado con los primeros 25 artworks (2026-10-29). Los que aun salgan mal se corrigen con "Cara"."""
    ilu = _zona_cara(ilustracion)
    alto, ancho = ilu.shape[:2]
    lado = int(ancho * LADO_CARA)
    lab = cv2.cvtColor(ilu, cv2.COLOR_BGR2LAB).astype(np.float32)
    borde = np.concatenate([lab[:15].reshape(-1, 3), lab[:, :10].reshape(-1, 3), lab[:, -10:].reshape(-1, 3)])
    figura = np.linalg.norm(lab - np.median(borde, 0), axis=2) > 28
    hsv = cv2.cvtColor(ilu, cv2.COLOR_BGR2HSV).astype(np.int16)
    piel = figura & (hsv[..., 0] <= 20) & (hsv[..., 1] >= 25) & (hsv[..., 1] <= 140) & (hsv[..., 2] >= 160)
    piel = cv2.morphologyEx(piel.astype(np.uint8), cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    figura = cv2.morphologyEx(figura.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    filas = np.where(figura.sum(1) > 8)[0]
    arriba = int(filas[0]) if filas.size else 0
    banda = figura[arriba:arriba + int(lado * 0.6)].sum(0)
    centro = int(np.average(np.arange(ancho), weights=banda)) if banda.sum() else ancho // 2
    x0 = max(0, min(ancho - lado, centro - lado // 2))
    y0 = max(0, min(alto - lado, arriba - 10))
    n, _, stats, centros = cv2.connectedComponentsWithStats(piel)
    caras = [i for i in range(1, n) if stats[i, 4] > 500 and stats[i, 1] < alto * 0.55]
    dentro = [i for i in caras if x0 <= centros[i][0] <= x0 + lado and y0 <= stats[i, 1] <= y0 + lado * 0.7]
    if caras and not dentro:
        i = min(sorted(caras, key=lambda k: -stats[k, 4])[:3], key=lambda k: stats[k, 1])
        return cara_en(ilustracion, int(centros[i][0]), int(stats[i, 1] + stats[i, 3] * 0.4) + BORDE_ARRIBA)
    return ilu[y0:y0 + lado, x0:x0 + lado].copy()


def guardar_cara(pid: str, cara: np.ndarray, catalogo: dict) -> None:
    """La cara de un heroe capturado, en su carpeta y en su personaje (pagina Personajes)."""
    guardar_imagen(C.CARPETA / pid / P.CARA_ARTWORK, cara)
    destino = C._existente(catalogo[pid], P.cargar(), P._leer_yaml(P.BASE), list(catalogo.values())) or pid
    guardar_imagen(P.CARPETA / destino / P.CARA_ARTWORK, cara)


def rehacer_caras(catalogo: dict) -> int:
    """Vuelve a recortar la cara de todos los artworks guardados (al mejorar recorte_cara)."""
    hechas = 0
    for pid in catalogo:
        ilustracion = leer_imagen(C.CARPETA / pid / ARTWORK)
        if ilustracion is not None and not catalogo[pid].get("cara_a_mano"):
            guardar_cara(pid, recorte_cara(ilustracion), catalogo)
            hechas += 1
    return hechas


def pasar_caras(catalogo: dict) -> int:
    """Copia cara_artwork.jpg (Inicio) y artwork.jpg (pagina Personajes) de cada heroe capturado a su personaje.
    Devuelve cuantas caras."""
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
        if (C.CARPETA / pid_captura / ARTWORK).is_file():
            shutil.copyfile(C.CARPETA / pid_captura / ARTWORK, P.CARPETA / destino / P.ARTWORK)
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
        return C.id_por_clave(self.catalogo, clave, C.atributo_por_icono(p))

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
        # Como mucho 5 s: el arma de Milim Nava cruza la fila de cartas y no se queda quieta nunca.
        if not self._quieta(p, C.ZONAS_ESTABLES[0]) and time.time() - self.desde < 5:
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
            self.log(f"Vuelvo al primer héroe: terminado ({self.hechos} héroes).", "ok")
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

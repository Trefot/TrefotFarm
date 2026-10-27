"""Captura de heroes en serie (solo administrador): recorre las fichas del juego y guarda cada heroe.

En el juego: Heroes -> abrir la ficha de un heroe. El bot lee el nombre, el titulo, Attribute, Race y
Characteristics (OCR de Windows), recorta las cartas de la fila Skills, abre Skill Info para leer el
nombre y la descripcion de cada carta, y pasa al siguiente heroe con la flecha de la derecha. Termina
al volver a un heroe ya capturado.

Todo se guarda aparte, en capturas/heroes (catalogo.yaml + imagenes), para revisarlo antes de
publicarlo en la base del bot.
"""

import re
import time

import numpy as np
import yaml

from trefot import entrada, juego, ocr
from trefot import personajes as P
from trefot.control import control
from trefot.motor import Modo, TerminarModo
from trefot.rutas import RAIZ
from trefot.vision import Plantilla, guardar_imagen

CARPETA = RAIZ / "capturas" / "heroes"
CATALOGO = CARPETA / "catalogo.yaml"

FICHA = Plantilla("heroes/ficha_attribute.png")  # la palabra "Attribute" de la ficha del heroe
SKILL_INFO = Plantilla("heroes/skill_info.png")  # titulo de la ventana Skill Info
CERRAR = Plantilla("heroes/cerrar.png")  # la X roja de Skill Info

# Medido en capturas reales de 550x940 (Wanderer Thonar, Gawain).
CABECERA = (130, 125, 445, 195)  # [titulo] y nombre
DATOS = (30, 300, 300, 388)  # Attribute, Race y Characteristics con sus valores
ETIQUETAS = ("attribute", "race", "characteristics")
PANEL_SKILL = (60, 440, 490, 720)  # nombre y descripcion de la carta en Skill Info
ZONA_ESTABLE = (20, 120, 530, 720)
FLECHA_HEROE = (510, 158)  # siguiente heroe
FLECHA_SKILL = (508, 463)  # siguiente carta dentro de Skill Info
MAX_CARTAS = 8
DIFERENCIA_ESTABLE = 3.0  # media de diferencia entre dos capturas para dar la pantalla por quieta

COLOR = {"strength": "rojo", "speed": "azul", "hp": "verde", "light": "claro", "dark": "oscuro"}
RAZA_ES = {"human": "humano", "giant": "gigante", "fairy": "hada", "goddess": "diosa", "demon": "demonio",
           "unknown": "desconocida"}


# ---------------------------------------------------------------- lectura (sin tocar el juego)
def limpiar_titulo(linea: str) -> str:
    """'[Battle-Hardened Mercenaryl' -> 'Battle-Hardened Mercenary' (el OCR a veces lee ']' como l)."""
    t = linea.strip().lstrip("[").strip()
    if t.endswith("]"):
        t = t[:-1]
    elif t[-1:] in ("l", "I", "|", "1", "J") and "]" not in t:
        t = t[:-1]
    return t.strip()


def leer_cabecera(pantalla) -> tuple[str, str]:
    lineas = ocr.leer_region(pantalla, CABECERA)
    titulo = next((limpiar_titulo(l) for l in lineas if l.startswith("[")), "")
    nombre = next((l for l in lineas if not l.startswith("[")), "")
    return titulo, nombre.strip()


def leer_datos(pantalla) -> tuple[str, str, str]:
    """(atributo, raza, caracteristicas). Cada valor se reconoce por lo que es, no por su posicion."""
    atributo = raza = ""
    otros = []
    for linea in ocr.leer_region(pantalla, DATOS):
        if linea.lower() in ETIQUETAS:
            continue
        # el icono de al lado a veces sale como una letra suelta: "O Light", "o"
        valor = re.sub(r"^[^A-Za-z\[]*(?:[A-Za-z]\s+)?(?=[A-Z\[])", "", linea).strip()
        if len(valor) <= 2:
            continue
        palabra = valor.lower()
        if not atributo and palabra in COLOR:
            atributo = valor
        elif not raza and palabra in RAZA_ES:
            raza = valor
        else:
            otros.append(valor.strip("[]. ").rstrip("."))
    return atributo, raza, " ".join(otros)


def tipo_de_carta(texto: str) -> str:
    t = texto.lower()
    if "all enemies" in t:
        return "area"
    if "one enemy" in t or "an enemy" in t or "single enemy" in t:
        return "single"
    if "all allies" in t or "an ally" in t or "allies" in t:
        return "apoyo"
    return "otro"


def leer_skill(pantalla) -> dict | None:
    """Nombre, descripcion y tipo de la carta abierta en Skill Info (None si no se lee el nombre)."""
    lineas = ocr.leer_region(pantalla, PANEL_SKILL, invertir=True)
    for i, linea in enumerate(lineas):
        nombre = re.search(r'["“”](.+?)["“”]', linea)
        if not nombre:
            continue
        descripcion = []
        for resto in lineas[i + 1:]:
            if re.match(r"^l?v\.?\s*\d+\s*/\s*\d+$", resto.lower()) or resto.lower().startswith(("preview", "two adjacent")):
                continue
            descripcion.append(resto)
        texto = " ".join(descripcion)
        return {"nombre": nombre.group(1).strip(), "ulti": linea.lower().startswith(("lv", "iv")),
                "texto": texto, "tipo": tipo_de_carta(texto)}
    return None


def recorte_carta(pantalla, i: int):
    x1, y1, x2, y2 = juego.FICHA_CARTAS[i]
    return pantalla[y1:y2, x1:x2].copy()


def cargar_catalogo() -> dict:
    if not CATALOGO.is_file():
        return {}
    with CATALOGO.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def guardar_catalogo(catalogo: dict) -> None:
    CARPETA.mkdir(parents=True, exist_ok=True)
    CATALOGO.write_text(yaml.safe_dump(catalogo, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")


# ------------------------------------------------------------------------------- el modo
class CapturaHeroes(Modo):
    id = "captura_heroes"
    nombre = "Captura de héroes"
    titulo_juego = "Captura de héroes"
    descripcion = "Recorre las fichas de los héroes y guarda nombre, datos y cartas de cada uno."
    guardar_historial = False
    pausa_entre_pasos = 0.3
    nombres_estados = {
        "buscar_ficha": "Esperando la ficha de un héroe",
        "leer_ficha": "Leyendo la ficha",
        "leer_cartas": "Leyendo las cartas (Skill Info)",
        "cerrar": "Cerrando Skill Info",
        "siguiente": "Pasando al siguiente héroe",
    }

    def __init__(self, valores: dict):
        super().__init__(valores)
        self.catalogo = cargar_catalogo()
        self.vistos: set[str] = set()
        self.capturados = 0
        self.actual: dict | None = None
        self.anterior = None
        self.esperando_desde = time.time()
        self.intentos = 0
        self.ultima_clave = ""  # el heroe recien guardado (tras la flecha puede seguir en pantalla un momento)
        self.repetida = 0

    def estado_inicial(self):
        return "buscar_ficha"

    def estados(self):
        return {
            "buscar_ficha": self.buscar_ficha,
            "leer_ficha": self.leer_ficha,
            "leer_cartas": self.leer_cartas,
            "cerrar": self.cerrar,
            "siguiente": self.siguiente,
        }

    # ------------------------------------------------------------------ utilidades
    def _quieta(self, pantalla) -> bool:
        """True si la pantalla no cambio desde la captura anterior (terminaron las animaciones)."""
        x1, y1, x2, y2 = ZONA_ESTABLE
        zona = pantalla[y1:y2, x1:x2].astype(np.int16)
        quieta = self.anterior is not None and self.anterior.shape == zona.shape and \
            float(np.abs(zona - self.anterior).mean()) < DIFERENCIA_ESTABLE
        self.anterior = zona
        return quieta

    def _id_para(self, clave: str, nombre: str, color: str) -> str:
        for pid, datos in self.catalogo.items():
            if datos.get("clave") == clave:
                return pid
        return P.nuevo_id(f"{nombre} {color}", self.catalogo)

    # ------------------------------------------------------------------ estados
    def buscar_ficha(self, p, o):
        if not ocr.disponible():
            self.log("Falta el OCR de Windows (paquetes winrt). Actualiza o ejecuta Instalar.bat.", "error")
            raise TerminarModo()
        if SKILL_INFO.esta(p, 0.85):
            return "cerrar"
        if FICHA.esta(p, 0.85):
            self.anterior = None
            return "leer_ficha"
        if time.time() - self.esperando_desde > 90:
            self.log("No veo la ficha de ningún héroe. Ábrela en el juego (Heroes -> un héroe) y vuelve a empezar.", "error")
            raise TerminarModo()
        return None

    def leer_ficha(self, p, o):
        if not FICHA.esta(p, 0.85) or not self._quieta(p):
            return None
        titulo, nombre = leer_cabecera(p)
        atributo, raza, caracteristicas = leer_datos(p)
        if not nombre or not atributo:
            self.intentos += 1
            if self.intentos >= 4:
                self.log("No pude leer el nombre de este héroe: lo salto.", "aviso")
                self.intentos = 0
                guardar_imagen(CARPETA / "sin_leer" / f"{time.strftime('%H%M%S')}.jpg", p)
                return "siguiente"
            return None
        self.intentos = 0
        clave = f"[{titulo}] {nombre}" if titulo else nombre
        if clave == self.ultima_clave:
            # Sigue el heroe anterior: la flecha aun no cambio la ficha (o no funciono).
            self.repetida += 1
            if self.repetida == 8:
                entrada.clic(FLECHA_HEROE, o, espera=1.0)
            if self.repetida > 16:
                self.log("La flecha no pasa al siguiente héroe: termino aquí.", "aviso")
                raise TerminarModo()
            return None
        self.repetida = 0
        if clave in self.vistos:
            self.log(f"Volví a {clave}: ya recorrí todos.", "ok")
            raise TerminarModo()
        self.vistos.add(clave)
        color = COLOR.get(atributo.lower().strip(), "sin definir")
        self.actual = {
            "clave": clave, "titulo": titulo, "nombre": nombre, "atributo": atributo, "color": color,
            "raza_juego": raza, "raza": RAZA_ES.get(raza.lower().strip(), "sin definir"),
            "caracteristicas": caracteristicas,
            "cartas": [], "_recortes": [recorte_carta(p, i) for i in range(len(juego.FICHA_CARTAS))],
            "_ficha": p.copy(),
        }
        self.log(f"Héroe: {clave} · {atributo} · {raza}")
        entrada.clic(_centro(juego.FICHA_CARTAS[0]), o, espera=0.6)
        return "leer_cartas"

    def leer_cartas(self, p, o):
        if not SKILL_INFO.esta(p, 0.85):
            self.intentos += 1
            if self.intentos % 6 == 0:  # el clic en la carta no abrio Skill Info: otra vez
                entrada.clic(_centro(juego.FICHA_CARTAS[0]), o, espera=0.6)
            if self.intentos > 20:
                self.log("Skill Info no se abre: guardo el héroe sin la descripción de sus cartas.", "aviso")
                self.intentos = 0
                self._guardar_actual()
                return "siguiente"
            return None
        if not self._quieta(p):
            return None
        self.intentos = 0
        carta = leer_skill(p)
        cartas = self.actual["cartas"]
        if carta is None:
            self.log("No pude leer esta carta; paso a la siguiente.", "aviso")
        elif any(c["nombre"] == carta["nombre"] for c in cartas) or len(cartas) >= MAX_CARTAS:
            return "cerrar"
        else:
            cartas.append(carta)
            tipo = "Ultimate" if carta["ulti"] else carta["tipo"]
            self.log(f"   Carta {len(cartas)}: {carta['nombre']} ({tipo})", "debug")
        entrada.clic(FLECHA_SKILL, o, espera=0.5)
        self.anterior = None
        return None

    def cerrar(self, p, o):
        if SKILL_INFO.esta(p, 0.85):
            self.clic_si(CERRAR, p, o, umbral=0.8, espera=0.5)
            return None
        if self.actual is None:  # Skill Info estaba abierto al empezar
            self.anterior = None
            return "leer_ficha"
        self._guardar_actual()
        return "siguiente"

    def siguiente(self, p, o):
        entrada.clic(FLECHA_HEROE, o, espera=1.0)
        self.anterior = None
        self.esperando_desde = time.time()
        return "leer_ficha"

    # ------------------------------------------------------------------ guardar
    def _guardar_actual(self):
        h = self.actual
        self.actual = None
        pid = self._id_para(h["clave"], h["nombre"], h["color"])
        carpeta = CARPETA / pid
        for i, recorte in enumerate(h.pop("_recortes"), start=1):
            guardar_imagen(carpeta / f"carta_{i}{P.SUFIJO_FICHA}.png", recorte)
        guardar_imagen(carpeta / "ficha.jpg", h.pop("_ficha"))
        h["capturado"] = time.strftime("%Y-%m-%d %H:%M")
        self.catalogo[pid] = h
        guardar_catalogo(self.catalogo)
        self.capturados += 1
        self.ultima_clave = h["clave"]
        control.actividad()
        self.log(f"Guardado {h['nombre']} ({len(h['cartas'])} cartas). Llevo {self.capturados}.", "ok")

    def al_terminar(self):
        self.log(f"Captura terminada: {self.capturados} héroes en capturas\\heroes (catálogo: {len(self.catalogo)}).", "ok")


def _centro(rect) -> tuple[int, int]:
    x1, y1, x2, y2 = rect
    return (x1 + x2) // 2, (y1 + y2) // 2

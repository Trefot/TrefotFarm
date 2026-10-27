"""Captura de objetos (administrador): recorre el inventario del juego y guarda cada objeto.

Empieza con el inventario abierto (Menu -> Inventory). Por cada categoria (Ingredients, Cooking, 1-Use,
Misc., Equipment) toca cada objeto de la estanteria, lee su ficha con el OCR de Windows (nombre, tipo y
descripcion) y recorta su icono; luego la cierra con la X. Nunca toca "Sell", "Location" ni "Go Now".

- Los objetos repetidos (varios montones del mismo) se saltan sin abrirlos: se compara el dibujo de la
  casilla con los ya vistos.
- La estanteria baja de 2 en 2 filas; si al arrastrar no se mueve, la categoria termino. Tocar una
  casilla vacia no abre nada: tambien es el final (el juego ordena los objetos sin huecos).

Guarda en capturas/objetos/galeria.yaml y capturas/objetos/<id>_ficha.png. Con esa galeria el botin
de cada pelea se nombra solo (ver lumen/botin.py).
"""

import re
import time

import cv2

from lumen import botin, entrada, ocr
from lumen.control import control
from lumen.motor import Modo, TerminarModo
from lumen.vision import Plantilla, guardar_imagen

INVENTARIO = Plantilla("objetos/inventario.png")  # boton "Sell Multiple" de la lista (solo para reconocerla)
CERRAR_FICHA = Plantilla("objetos/cerrar_ficha.png")  # la X roja de la ficha de un objeto
CATEGORIAS = [("Ingredients", (72, 215)), ("Cooking", (173, 215)), ("1-Use", (273, 215)),
              ("Misc.", (382, 215)), ("Equipment", (478, 215))]
# Estanteria: 4 columnas y filas cada 130 px (medido en la ventana de 554x960).
COLUMNAS = (85, 210, 337, 470)
FILAS = (375, 505, 635, 765)
PASO_FILA = 130
PARECIDO_CASILLA = 0.93  # dibujo de casilla ya visto (mismo objeto en otro monton o tras bajar)
ESPERA_FICHA = 3.0  # sin ficha tras tocar = casilla vacia


def recorte_casilla(pantalla, cx: int, cy: int):
    """El dibujo del objeto en la estanteria, sin el numero de la cantidad (abajo a la derecha)."""
    return pantalla[cy - 45 : cy + 12, cx - 42 : cx + 42].copy()


def leer_ficha(pantalla, x_cerrar: int, y_cerrar: int) -> dict:
    """Icono, nombre, tipo, descripcion y cantidad de la ficha (todo relativo a la X de cerrar)."""
    icono = pantalla[y_cerrar + 9 : y_cerrar + 95, x_cerrar - 197 : x_cerrar - 111].copy()
    lineas = ocr.leer(pantalla[y_cerrar + 95 : y_cerrar + 400, x_cerrar - 350 : x_cerrar + 40])
    cantidad = 0
    for i, linea in enumerate(lineas):
        if "owned" in linea.lower():
            cantidad = int(re.sub(r"\D", "", linea) or 0)
            lineas = lineas[i + 1 :]
            break
    resto = []
    for linea in lineas:
        if re.fullmatch(r"\W*(location|sell)\W*", linea.strip().lower()):
            break
        resto.append(linea.strip())
    nombre = resto[0] if resto else ""
    tipo = resto[1] if len(resto) > 1 else ""
    descripcion = " ".join(resto[2:])
    return {"icono": icono, "nombre": nombre, "tipo": tipo, "descripcion": descripcion, "cantidad": cantidad}


def id_de(nombre: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", nombre.lower()).strip("_") or "objeto"


class CapturaObjetos(Modo):
    id = "captura_objetos"
    nombre = "Captura de objetos"
    titulo_juego = "Captura de objetos"
    descripcion = "Recorre el inventario y guarda nombre, tipo, descripción e icono de cada objeto."
    guardar_historial = False
    pausa_entre_pasos = 0.3
    nombres_estados = {
        "empezar": "Buscando el inventario",
        "categoria": "Abriendo una categoría",
        "recorrer": "Recorriendo la estantería",
        "esperar_ficha": "Leyendo un objeto",
        "cerrar": "Cerrando la ficha",
    }

    def __init__(self, valores: dict):
        super().__init__(valores)
        self.galeria = botin.cargar_galeria_local()
        self.categoria = 0
        self.vistos: list = []  # recortes de casilla ya tratados en esta categoria
        self.casilla = 0  # siguiente casilla de esta pagina (0..15)
        self.tocada: tuple | None = None
        self.desde = time.time()
        self.nuevos = self.leidos = 0

    def estado_inicial(self):
        return "empezar"

    def estados(self):
        return {"empezar": self.empezar, "categoria": self.abrir_categoria, "recorrer": self.recorrer,
                "esperar_ficha": self.esperar_ficha, "cerrar": self.cerrar}

    # ------------------------------------------------------------------ estados
    def empezar(self, p, o):
        rect = CERRAR_FICHA.buscar(p, 0.85)
        if rect is not None:  # habia una ficha abierta: cerrarla
            entrada.clic((int(rect[0] + rect[2] // 2), int(rect[1] + rect[3] // 2)), o, espera=1.0)
            return None
        if not INVENTARIO.esta(p, 0.85):
            self.log("No veo el inventario. Ábrelo en el juego (Menu -> Inventory) y vuelve a empezar.", "error")
            raise TerminarModo()
        self.log("Inventario encontrado: empiezo por Ingredients.", "ok")
        return "categoria"

    def abrir_categoria(self, p, o):
        if self.categoria >= len(CATEGORIAS):
            raise TerminarModo()
        nombre, punto = CATEGORIAS[self.categoria]
        entrada.clic(punto, o, espera=1.5)
        self.vistos, self.casilla = [], 0
        self.log(f"Categoría {nombre}.", "ok")
        return "recorrer"

    def recorrer(self, p, o):
        if not INVENTARIO.esta(p, 0.85):
            return None  # aun se cierra una ficha o cambia la categoria
        while self.casilla < len(COLUMNAS) * len(FILAS):
            fila, columna = divmod(self.casilla, len(COLUMNAS))
            cx, cy = COLUMNAS[columna], FILAS[fila]
            recorte = recorte_casilla(p, cx, cy)
            self.casilla += 1
            if any(float(cv2.matchTemplate(recorte, v, cv2.TM_CCOEFF_NORMED).max()) >= PARECIDO_CASILLA for v in self.vistos):
                continue  # mismo objeto que otro ya leido
            self.vistos.append(recorte)
            self.tocada = (cx, cy)
            entrada.clic((cx, cy), o, espera=0.8)
            self.desde = time.time()
            return "esperar_ficha"
        # Pagina terminada: bajar 2 filas. Si la estanteria no se mueve, la categoria termino.
        antes = p[330:830].copy()
        entrada.arrastrar((275, 700), (275, 700 - 2 * PASO_FILA), o, duracion=0.9)
        control.esperar(1.5)
        despues = self.capturar()[0][330:830]
        if float(cv2.absdiff(antes, despues).mean()) < 4:
            return self._siguiente_categoria()
        self.casilla = 0
        return None

    def esperar_ficha(self, p, o):
        rect = CERRAR_FICHA.buscar(p, 0.85)
        if rect is None:
            if time.time() - self.desde > ESPERA_FICHA:
                self.log("Casilla vacía: se acabaron los objetos de esta categoría.", "debug")
                return self._siguiente_categoria()
            return None
        control.esperar(0.4)  # que termine de abrirse
        p = self.capturar()[0]
        rect = CERRAR_FICHA.buscar(p, 0.85)
        if rect is None:
            return None
        x, y = int(rect[0]), int(rect[1])
        try:
            ficha = leer_ficha(p, x, y)
        except Exception as error:
            ficha = {"nombre": "", "error": str(error)}
        if ficha.get("nombre"):
            gid = id_de(ficha["nombre"])
            nuevo = gid not in self.galeria
            self.galeria[gid] = {
                "nombre": ficha["nombre"], "tipo": ficha["tipo"], "descripcion": ficha["descripcion"],
                "categoria": CATEGORIAS[self.categoria][0], "cantidad": ficha["cantidad"],
                "capturado": time.strftime("%Y-%m-%d %H:%M"),
            }
            botin.guardar_ficha(gid, ficha["icono"])
            botin.guardar_galeria_local(self.galeria)
            self.leidos += 1
            self.nuevos += nuevo
            self.publicar_stats(objetos=self.leidos, nuevos=self.nuevos)
            self.log(f"{ficha['nombre']} · {ficha['tipo']}", "ok")
        else:
            guardar_imagen(botin.CARPETA_GALERIA / "sin_leer" / f"{time.strftime('%H%M%S')}.jpg", p)
            self.log("No pude leer este objeto: guardé la foto en capturas\\objetos\\sin_leer.", "aviso")
        entrada.clic((x + int(rect[2]) // 2, y + int(rect[3]) // 2), o, espera=0.8)  # la X, nunca Sell
        self.desde = time.time()
        return "cerrar"

    def cerrar(self, p, o):
        if CERRAR_FICHA.esta(p, 0.85):
            if time.time() - self.desde > 4:  # la X no respondio: otra vez
                rect = CERRAR_FICHA.buscar(p, 0.85)
                entrada.clic((int(rect[0] + rect[2] // 2), int(rect[1] + rect[3] // 2)), o, espera=0.8)
                self.desde = time.time()
            return None
        return "recorrer"

    def _siguiente_categoria(self):
        self.categoria += 1
        return "categoria"

    def al_terminar(self):
        self.log(f"Captura de objetos terminada: {self.leidos} leídos ({self.nuevos} nuevos). "
                 f"Galería: {len(self.galeria)} objetos.", "ok")

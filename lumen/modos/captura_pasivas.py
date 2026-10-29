"""Captura de gracias, pasivas y reliquias (solo administrador), para que la IA sepa lo que hace cada heroe.

Recorre las fichas como la captura de artworks (desde la ficha de un heroe, flecha a la derecha, termina al
volver al primero). En cada ficha toca los iconos de la fila "Grace / Unique": la Gracia, la pasiva unica
(Unique) y la Reliquia (Holy Relic), y algun otro si lo hay. De cada ventana lee el nombre y el texto, la
cierra con la X y sigue. Medido con Covenant of Light Ludociel (capturas del 2026-10-29).

Se guarda en capturas/heroes/catalogo.yaml, en cada heroe: ``gracia`` y ``pasiva`` ({nombre, texto}),
``reliquias`` ([{nombre, efecto}]), ``talento``, ``unidad`` y ``mandamiento`` si los tiene, y ``otras`` (con otro
titulo). El orden de los iconos cambia segun el heroe (Nemesis Meliodas no tiene Gracia y si Talent): cada
ventana se reconoce por su titulo.
"""

import re
import time

import cv2
import numpy as np

from lumen import entrada, ocr
from lumen.control import control
from lumen.modos import captura_heroes as C
from lumen.modos.captura_artworks import CapturaArtworks
from lumen.vision import Plantilla, guardar_imagen

CERRAR = Plantilla("heroes/cerrar_ventana.png")  # la X roja de las ventanas de Gracia, Unique y Reliquia
MAS_TEXTO = Plantilla("heroes/flecha_mas_texto.png")  # flecha amarilla bajo un texto largo: hay que deslizar
PAGINAS_MAX = 6  # "The Final Battle" de Meliodas necesita varias
# Iconos de la fila "Grace / Unique" (ficha de 550x940): Gracia, Unique, Reliquia y un hueco mas por si acaso
ICONOS = ((80, 785), (157, 785), (240, 785), (320, 785))
COLUMNAS_TEXTO = (70, 480)
TITULOS = (("grac", "gracia"), ("uniq", "pasiva"), ("talent", "talento"), ("unity", "unidad"),
           ("command", "mandamiento"))
TIPOS_UNICOS = ("gracia", "pasiva", "talento", "unidad", "mandamiento")  # uno por heroe


def es_marca_reliquia(linea: str) -> bool:
    """"Holy Relic Effect", tambien mal leido ("HotyRer•Cffect", "Holy kenc Effect"; captura del 2026-10-29)."""
    l = linea.lower().strip()
    return "holy relic" in l or "relic effect" in l or (l.startswith("ho") and re.search(r"[ce]ffect$", l) is not None)
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
    titulo = cabecera[0] if cabecera else ""
    # El orden de los iconos cambia (Nemesis Meliodas: sin Gracia, Unique y Talent): manda el titulo. "Unique"
    # gana aunque el texto hable de reliquias (la pasiva de Mage of Infinity Merlin las nombra).
    tipo = next((t for clave, t in TITULOS if titulo.lower().startswith(clave)), "otra")
    if tipo == "otra" and any(es_marca_reliquia(l) for l in cabecera + cuerpo[:2]):
        tipo = "reliquia"
        nombre = next((l for l in reversed(cabecera) if not es_marca_reliquia(l)), "")
        cuerpo = [l for l in cuerpo if not es_marca_reliquia(l)]
    else:
        # La gracia lleva encima el titulo del heroe ("[Advent of Flash]"), a veces medio tapado y leido como
        # "(Advent of FhcN": esa linea no es el nombre (Ludociel, 2026-10-29).
        while cuerpo and re.match(r"^[\[(]", cuerpo[0]) and len(cuerpo) > 1:
            cuerpo = cuerpo[1:]
        nombre, cuerpo = (cuerpo[0], cuerpo[1:]) if cuerpo else ("", [])
        nombre = re.sub(r"^\[.*?\]\s*", "", nombre)
    return {"tipo": tipo, "titulo": titulo, "nombre": nombre, "lineas": cuerpo, "texto": unir(cuerpo)}


def unir(lineas: list[str]) -> str:
    return re.sub(r"\s+", " ", " ".join(lineas)).strip()


def _igual(a: str, b: str) -> bool:
    return re.sub(r"\W", "", a.lower()) == re.sub(r"\W", "", b.lower())


def juntar(previas: list[str], nuevas: list[str]) -> list[str]:
    """Las lineas de un texto largo leido en dos trozos (antes y despues de deslizar), sin repetir las que
    se ven en los dos: se busca el solape mas largo entre el final de las primeras y el principio de las otras."""
    for k in range(min(len(previas), len(nuevas)), 0, -1):
        if all(_igual(a, b) for a, b in zip(previas[-k:], nuevas[:k])):
            return previas + nuevas[k:]
    return previas + [n for n in nuevas if not any(_igual(n, a) for a in previas)]


def normalizar(h: dict) -> bool:
    """Ordena lo leido de un heroe (tambien lo capturado antes de estas reglas). Devuelve si cambio algo:
    - "otras" con titulo Commandment -> ``mandamiento``; con la marca de reliquia mal leida -> ``reliquias``
      (su nombre es el titulo); repetidas -> una vez;
    - una "reliquia" llamada "Unique" era la pasiva (Mage of Infinity Merlin);
    - sin pasiva, la ventana con el titulo ilegible es la pasiva (Captain Hawk: "I'll Eat You Up!")."""
    antes = repr(h)
    otras, vistas = [], set()
    for o in h.get("otras") or []:
        clave = (o.get("nombre", ""), o.get("texto", "")[:60])
        if clave in vistas:
            continue
        vistas.add(clave)
        titulo = (o.get("titulo") or "").lower()
        if titulo.startswith("command"):
            h.setdefault("mandamiento", {"nombre": o.get("nombre", ""), "texto": o.get("texto", "")})
        elif es_marca_reliquia(o.get("nombre", "")) or es_marca_reliquia(
                " ".join([o.get("nombre", "")] + o.get("texto", "").split()[:2])):  # "Holy" + "Rellc affect ..."
            texto = re.sub(r"^\S*\s+[ae]ffect\s+", "", o.get("texto", "")) if not es_marca_reliquia(o.get("nombre", "")) \
                else o.get("texto", "")
            h.setdefault("reliquias", []).append({"nombre": o.get("titulo", ""), "efecto": texto})
        else:
            otras.append(o)
    reliquias = []
    for r in h.get("reliquias") or []:
        if r.get("nombre", "").lower().startswith("uniq") and not h.get("pasiva"):
            h["pasiva"] = {"nombre": "", "texto": r.get("efecto", "")}
        elif not any(x.get("nombre") == r.get("nombre") for x in reliquias):
            reliquias.append(r)
    if not h.get("pasiva") and otras:
        o = otras.pop(0)
        h["pasiva"] = {"nombre": o.get("nombre", ""), "texto": o.get("texto", "")}
    for clave, valor in (("reliquias", reliquias), ("otras", otras)):
        if valor:
            h[clave] = valor
        else:
            h.pop(clave, None)
    return repr(h) != antes


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
        self.paginas = 0

    def estados(self):
        return {"ficha": self.ficha, "leer": self.leer, "leer_mas": self.leer_mas, "cerrado": self.cerrado,
                "volver": self.volver}

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
            self.paginas = 1
            if MAS_TEXTO.esta(p, 0.85):
                return self._deslizar(p, o)
        else:
            guardar_imagen(C.CARPETA / "sin_leer" / f"pasiva_{time.strftime('%H%M%S')}.jpg", p)
            self.log("No pude leer esta ventana (guardo la captura en capturas/heroes/sin_leer).", "aviso")
        return self._cerrar(rect, o)

    def _cerrar(self, rect, o):
        entrada.clic((int(rect[0] + rect[2] // 2), int(rect[1] + rect[3] // 2)), o, espera=0.8)
        self.icono += 1
        self.desde = time.time()
        return "cerrado"

    def _deslizar(self, p, o):
        """Texto largo (flecha amarilla abajo): subirlo para leer el resto (2026-10-29, Bargaining With the Gods)."""
        y1, y2 = zona_texto(p) or (360, 740)
        entrada.arrastrar((275, y2 - 30), (275, y1 + 80), o, duracion=0.6)
        control.esperar(0.8)
        return "leer_mas"

    def leer_mas(self, p, o):
        rect = CERRAR.buscar(p, 0.85)
        banda = zona_texto(p)
        if rect is None or banda is None:
            return "cerrado"
        x1, x2 = COLUMNAS_TEXTO
        nuevas = [l.strip() for l in leer_texto(p[banda[0]:banda[1], x1:x2]) if l.strip()]
        ventana = self.leidas[-1]
        ventana["lineas"] = juntar(ventana["lineas"], nuevas)
        ventana["texto"] = unir(ventana["lineas"])
        self.paginas += 1
        if MAS_TEXTO.esta(p, 0.85) and self.paginas < PAGINAS_MAX:
            return self._deslizar(p, o)
        return self._cerrar(rect, o)

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
            elif v["tipo"] in TIPOS_UNICOS:
                h[v["tipo"]] = {"nombre": v["nombre"], "texto": v["texto"]}
            else:
                h.setdefault("otras", []).append({"titulo": v["titulo"], "nombre": v["nombre"], "texto": v["texto"]})
        normalizar(h)
        h["pasivas_capturadas"] = time.strftime("%Y-%m-%d %H:%M")
        C.guardar_catalogo(self.catalogo)
        self.hechos += 1
        self._stats()
        tipos = ", ".join(v["tipo"] for v in self.leidas) or "nada"
        self.log(f"{h.get('nombre', self.actual)}: {tipos} ({self.hechos}).", "ok")
        return self._siguiente(o)

    def al_terminar(self):
        self.log(f"Gracias, pasivas y reliquias: {self.hechos} héroes leídos, {self.saltados} saltados.", "ok")

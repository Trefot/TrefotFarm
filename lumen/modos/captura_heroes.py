"""Captura de heroes en serie (solo administrador): recorre las fichas del juego y guarda cada heroe.

Si empieza en la lista de Heroes, primero recorta el icono de cada heroe en orden (bajando la lista) y
abre el primero; el icono k es el del heroe k, porque la flecha de la ficha sigue el orden de la lista
(se comprueba con el color del atributo). Si empieza en una ficha, se salta los iconos.

En cada ficha el bot lee el nombre, el titulo, Attribute, Race y
Characteristics (OCR de Windows), recorta las cartas de la fila Skills, abre Skill Info para leer el
nombre y la descripcion de cada carta, y pasa al siguiente heroe con la flecha de la derecha. Termina
al volver a un heroe ya capturado.

Todo se guarda aparte, en capturas/heroes (catalogo.yaml + imagenes), para revisarlo antes de
publicarlo en la base del bot.
"""

import difflib
import re
import time

import cv2
import numpy as np
import yaml

from lumen import entrada, juego, ocr
from lumen import personajes as P
from lumen.control import control
from lumen.motor import Modo, TerminarModo
from lumen.rutas import RAIZ
from lumen.vision import Plantilla, guardar_imagen, leer_imagen

CARPETA = RAIZ / "capturas" / "heroes"
CATALOGO = CARPETA / "catalogo.yaml"
CARAS = CARPETA / "iconos"  # fase 1: icono de cada heroe de la lista, numerado en orden (001.png...)

FICHA = Plantilla("heroes/ficha_attribute.png")  # la palabra "Attribute" de la ficha del heroe
SKILL_INFO = Plantilla("heroes/skill_info.png")  # titulo de la ventana Skill Info
CERRAR = Plantilla("heroes/cerrar.png")  # la X roja de Skill Info
LISTA = Plantilla("heroes/lista_search_skills.png")  # boton "Search Skills" de la lista de Heroes

# Lista de Heroes: rejilla de 5 columnas. Medido en una captura real de 550x940.
COLUMNAS_LISTA = (39, 136, 232, 329, 425)
LADO_CASILLA = 88
PASO_FILA = 95
PRIMERA_FILA = 221  # con la lista arriba del todo
LIMITE_LISTA = 700  # mas abajo pasa el cartel de avisos del juego por encima de las casillas
LIMITE_LISTA_FINAL = 745  # al final de la lista se acepta la ultima fila aunque el cartel la cruce
ARRIBA_LISTA = 100  # la lista se ve desde aqui (al deslizar, una fila puede quedar en y~140)
FILAS_POR_ARRASTRE = 2  # el juego sigue deslizando al soltar (3 filas de arrastre bajaban mas de 4)
ICONO_CASILLA = (64, 0, 88, 18)  # atributo, arriba a la derecha de la casilla
BORDE_CASILLA = 130  # punto mas claro del marco de arriba: LR plateado ~230, UR rojo 172-202; hueco vacio <=80

# Medido en capturas reales de 550x940 (Wanderer Thonar, Gawain).
CABECERA = (130, 125, 445, 195)  # [titulo] y nombre
DATOS = (30, 300, 300, 388)  # Attribute, Race y Characteristics con sus valores
ETIQUETAS = ("attribute", "race", "characteristics")
PANEL_SKILL = (60, 380, 490, 740)  # nombre y descripcion de la carta en Skill Info (sube si es larga)
# Antes de leer se espera a que la fila de cartas quede quieta. No sirve mirar mas: la figura del
# heroe se mueve todo el rato y en algunos (las alas de Ludociel) tapa los datos y el nombre.
ZONAS_ESTABLES = [(30, 595, 220, 700)]
ICONO_ATRIBUTO = (114, 307, 142, 331)
OSCURO = 80  # el texto de la ficha es oscuro; alas y brillos son claros y se borran por debajo de esto
LECTURAS_DATOS = 3  # capturas para votar la raza (las alas se mueven y cada una tapa otras letras)
ZONA_SKILL_INFO = (60, 440, 490, 720)
ESPERA_MAXIMA_QUIETA = 4.0  # s; si no se queda quieta, se lee igual
FLECHA_HEROE = (510, 158)  # siguiente heroe
VOLVER = (38, 62)  # flecha amarilla de arriba a la izquierda: de la ficha a la lista
MAX_CARTAS_SIN_LEER = 4  # seguidas; despues se pasa al siguiente heroe
FLECHA_SKILL = (508, 463)  # siguiente carta dentro de Skill Info
MAX_CARTAS = 8
DIFERENCIA_ESTABLE = 3.0  # media de diferencia entre dos capturas para dar la pantalla por quieta

COLOR = {"strength": "rojo", "speed": "azul", "hp": "verde", "light": "claro", "dark": "oscuro"}
RAZA_ES = {"human": "humano", "giant": "gigante", "fairy": "hada", "goddess": "diosa", "demon": "demonio",
           "unknown": "desconocida"}


# ---------------------------------------------------------------- lectura (sin tocar el juego)
def limpiar_titulo(linea: str) -> str:
    """'[Battle-Hardened Mercenaryl' -> 'Battle-Hardened Mercenary' (el OCR a veces lee ']' como l)."""
    t = linea.strip().lstrip("[(").strip()
    if t.endswith(("]", ")", "}")):
        t = t[:-1]
    elif t[-1:] in ("l", "I", "|", "1", "J") and "]" not in t:
        t = t[:-1]
    return t.strip()


def solo_texto_oscuro(imagen, umbral: int = OSCURO):
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    return np.where(gris < umbral, 0, 255).astype(np.uint8)


def quitar_brillo_ur(nombre: str) -> str:
    """'SBlessing of the Earth Diane' / 's Thor' -> sin la S: es el brillo del sello UR junto al nombre."""
    return re.sub(r"^(?:[sS$§]\s+|S(?=[A-Z][a-z]))", "", nombre)


def _titulo_y_nombre(lineas) -> tuple[str, str]:
    """El nombre es la linea de abajo y el titulo la de arriba. El titulo suele ir entre corchetes,
    pero no siempre ("Waves of the Earth" / Queen Diane)."""
    lineas = [l for l in lineas if len(l.strip()) > 1]
    if not lineas:
        return "", ""
    nombre = quitar_brillo_ur(lineas[-1].strip())
    if nombre.startswith("["):  # solo se leyo el titulo
        return limpiar_titulo(nombre), ""
    titulo = limpiar_titulo(lineas[-2]) if len(lineas) >= 2 else ""
    return titulo, nombre


def leer_cabecera(pantalla) -> tuple[str, str]:
    return leer_cabecera_varias([pantalla])


def leer_cabecera_varias(pantallas) -> tuple[str, str]:
    """[titulo] y nombre, votando entre varias lecturas: normal y solo con el texto oscuro (que borra
    alas y brillos de la figura pero a veces confunde una letra). Gana la que mas se repite."""
    x1, y1, x2, y2 = CABECERA
    votos_titulo: dict[str, int] = {}
    votos_nombre: dict[str, int] = {}
    for pantalla in pantallas:
        recorte = pantalla[y1:y2, x1:x2]
        lecturas = [ocr.leer(recorte)] + [ocr.leer(solo_texto_oscuro(recorte, u), escala=3) for u in (OSCURO, 110)]
        for lineas in lecturas:
            titulo, nombre = _titulo_y_nombre(lineas)
            if nombre:
                votos_nombre[nombre] = votos_nombre.get(nombre, 0) + 1
            if titulo:  # un titulo claro puede no salir en la lectura de texto oscuro: se vota aparte
                votos_titulo[titulo] = votos_titulo.get(titulo, 0) + 1
    titulo = max(votos_titulo, key=votos_titulo.get) if votos_titulo else ""
    nombre = max(votos_nombre, key=votos_nombre.get) if votos_nombre else ""
    return titulo, nombre


def leer_datos(pantalla) -> tuple[str, str, str]:
    """(atributo, raza, caracteristicas). Cada valor se reconoce por lo que es, no por su posicion."""
    atributo = raza = ""
    otros = []
    for linea in ocr.leer_region(pantalla, DATOS):
        if linea.lower() in ETIQUETAS:
            continue
        # el icono de al lado a veces sale como una letra suelta: "O Light", "o"
        valor = re.sub(r"^[^A-Za-z\[]*(?:[A-Za-z]\s+)?(?=[A-Z\[])", "", linea).strip()
        if len(valor) <= 2 or re.search(r"\d", valor) or re.search(r"combat|class|attack|defense", valor, re.I):
            continue
        palabra = valor.lower()
        if not atributo and palabra in COLOR:
            atributo = valor
        elif not raza and palabra in RAZA_ES:
            raza = valor
        elif not parecida(valor, COLOR, 0.75) and not parecida(valor, RAZA_ES, 0.75):  # atributo o raza mal leidos
            valor = re.sub(r"^characteristics\s*", "", valor, flags=re.I)
            otros.append(valor.strip("[]. ").rstrip("."))
    return atributo, raza, " ".join(otros)


def atributo_por_icono(pantalla) -> str:
    """Attribute por el color de su icono (no lo tapan las figuras): Speed azul, Light amarillo..."""
    x1, y1, x2, y2 = ICONO_ATRIBUTO
    return atributo_por_color(pantalla[y1:y2, x1:x2])


def atributo_por_color(icono, minimo: int = 60) -> str:
    """Medido en la ficha y en la lista: Speed ~100, HP ~50, Dark ~142, Strength ~4, Light ~20."""
    hsv = cv2.cvtColor(icono, cv2.COLOR_BGR2HSV)
    tonos = hsv[..., 0][hsv[..., 1] > 90]
    if tonos.size < minimo:
        return ""
    tono = float(np.median(tonos))
    if tono < 8 or tono >= 165:
        return "Strength"
    if tono < 40:
        return "Light"
    if tono < 90:
        return "HP"
    if tono < 130:
        return "Speed"
    return "Dark"


def parecida(texto: str, opciones, minimo: float = 0.5) -> str:
    """La opcion mas parecida al texto leido (o '' si ninguna se parece lo suficiente)."""
    limpio = re.sub(r"[^a-z]", "", texto.lower())
    encontradas = difflib.get_close_matches(limpio, list(opciones), n=1, cutoff=minimo)
    return encontradas[0] if encontradas else ""


def leer_datos_varias(pantallas) -> tuple[str, str, str]:
    """(atributo, raza, caracteristicas) votando entre varias capturas de la misma ficha."""
    icono = atributo_por_icono(pantallas[-1])
    votos_raza: dict[str, int] = {}
    caracteristicas = ""
    atributo_leido = ""
    for pantalla in pantallas:
        atributo, raza, otras = leer_datos(pantalla)
        atributo_leido = atributo_leido or atributo
        candidata = raza or next((parecida(l, RAZA_ES) for l in ocr.leer_region(pantalla, DATOS)
                                  if parecida(l, RAZA_ES)), "")
        if candidata:
            clave = candidata.lower()
            votos_raza[clave] = votos_raza.get(clave, 0) + 1
        if len(otras) > len(caracteristicas):
            caracteristicas = otras
    raza = max(votos_raza, key=votos_raza.get).capitalize() if votos_raza else ""
    return atributo_leido or icono, raza, caracteristicas


def tipo_de_carta(texto: str) -> str:
    """single / area / defensa / apoyo / otro. El OCR a veces desordena palabras ("on one Inflicts Pierce
    enemy"), asi que se busca "on one" / "on all" ademas de "one enemy" / "all enemies"."""
    t = texto.lower()
    if re.search(r"assumes a stance|\btaunt|\breflect", t):
        return "defensa"
    dano = t.find("damage equal")
    if dano >= 0:  # a quien pega el dano ("... damage equal to 200% of Attack on one enemy")
        objetivo = re.search(r"\b(?:on|to)\s+(one|all)\b|\b(one) enem|\b(all) enem", t[dano:])
        if objetivo:
            return "single" if "one" in objetivo.groups() else "area"
    if re.search(r"\bone enem", t):
        return "single"
    if "all enemies" in t:
        return "area"
    if "one enemy" in t or "an enemy" in t or "single enemy" in t:
        return "single"
    if "all allies" in t or "an ally" in t or "allies" in t:
        return "apoyo"
    return "otro"


def leer_skill(pantalla) -> dict | None:
    """Nombre, descripcion y tipo de la carta abierta en Skill Info (None si no se lee el nombre).
    El texto es claro sobre fondo oscuro; si asi no sale el nombre, se prueba sin invertir."""
    for invertir in (True, False):
        carta = _leer_skill(ocr.leer_region(pantalla, PANEL_SKILL, invertir=invertir))
        if carta:
            return carta
    return None


def reclasificar(catalogo: dict) -> bool:
    """Vuelve a clasificar las cartas con la regla actual (menos las que se corrigieron a mano)."""
    cambio = False
    for h in catalogo.values():
        if h.get("revisado"):
            continue
        for c in h.get("cartas") or []:
            tipo = tipo_de_carta(c.get("texto", ""))
            if tipo != c.get("tipo"):
                c["tipo"], cambio = tipo, True
    return cambio


COMILLAS = "\"“”‘’'*`´�"
ULTIMATE = re.compile(r"^\s*(?:max\s*)?l[vi1](?:\.|\s+\d)\s*\d*\s*", re.I)  # "Lv. 1 ..." / "MAX Lv. ..." (no "Lightning")


def nombre_de_carta(linea: str) -> tuple[str, bool] | None:
    leido = _nombre_de_carta(linea)
    if not leido:
        return None
    nombre = re.sub(r"^[^\w(]+|[^\w)!?]+$", "", leido[0])  # restos de comillas o simbolos en los bordes
    return (nombre, leido[1]) if len(nombre) >= 3 else None


def _nombre_de_carta(linea: str) -> tuple[str, bool] | None:
    """(nombre, es_ultimate) si la linea es la del nombre de la carta. Formatos vistos en el juego:
    '"Ruthless Violence"', 'Lv. 1 "X"', 'MAX Lv. "X"', 'Enchant: "Hellbringer"',
    'Spirit Spear Chastiefol, Third Form: "Fossilization"'. El OCR a veces cambia las comillas por ' o *.
    Se queda con lo de entre comillas (las formas de una misma lanza tienen nombres distintos)."""
    es_ulti = bool(ULTIMATE.match(linea))
    limpia = linea.strip().rstrip(".")
    if not es_ulti and limpia[:1] in "*※" and ":" in limpia[:40]:
        return None  # nota al pie de la descripcion ("*Sunfire: ...")
    forma = re.search(r",\s*\w+\s+form\s*:\s*(.+)$", linea, re.I)
    if forma:  # 'Spirit Spear Chastiefol, Eighth Form: "Pollen Garden"' (a veces la comilla sale como -)
        nombre = forma.group(1).strip(" -" + COMILLAS)
        return (nombre, es_ulti) if len(nombre) >= 3 else None
    entre = re.search(f"[{re.escape(COMILLAS)}](.+)[{re.escape(COMILLAS)}]", linea)  # de la primera a la ultima
    if entre and (es_ulti or limpia[:1] in COMILLAS or (limpia[-1:] in COMILLAS and len(limpia) <= 70)):
        nombre = entre.group(1)  # el nombre empieza o termina la linea (no comillas sueltas de la descripcion)
    elif es_ulti:
        resto = ULTIMATE.sub("", linea)
        forma = re.search(r",\s*\w+\s+form\b", resto, re.I)
        nombre = resto[:forma.start()] if forma else resto
    else:
        return None
    nombre = nombre.strip(" " + COMILLAS)
    return (nombre, es_ulti) if len(nombre) >= 3 else None


DESCRIPCION = re.compile(r"^(inflicts|increases|decreases|removes|restores|assumes|applies|grants|deals|recovers|"
                         r"taunts|reflects|creates|blocks|nullifies|heals|cleanses|attacks|depletes|steals)\b|\d+\s*%",
                         re.I)


def _sin_comillas(lineas) -> tuple[int, str] | None:
    """Algunas cartas no llevan comillas ("Tornado"): el nombre es la linea corta justo antes de la
    primera linea de descripcion."""
    for i, linea in enumerate(lineas):
        if DESCRIPCION.search(linea):
            if i == 0:
                return None
            nombre = lineas[i - 1].strip(" " + COMILLAS)
            if 3 <= len(nombre) <= 45 and "%" not in nombre and "adjacent skills" not in nombre.lower():
                return i - 1, nombre
            return None
    return None


def _leer_skill(lineas) -> dict | None:
    candidatos = []
    for i, linea in enumerate(lineas):
        if "adjacent skills" not in linea.lower():  # "Two adjacent skills..." (a veces "Tvqo adjacent")
            leido = nombre_de_carta(linea)
            if leido:
                candidatos.append((i, leido))
                break
    if not candidatos:
        sin = _sin_comillas(lineas)
        if sin:
            candidatos.append((sin[0], (sin[1], False)))
    for i, leido in candidatos:
        descripcion = []
        for resto in lineas[i + 1:]:
            if re.match(r"^l?v\.?\s*\d+\s*/\s*\d+$", resto.lower()) or resto.lower().startswith("preview")                     or "adjacent skills" in resto.lower():
                continue
            descripcion.append(resto)
        texto = " ".join(descripcion)
        return {"nombre": leido[0], "ulti": leido[1], "texto": texto, "tipo": tipo_de_carta(texto)}
    return None


# Fila "Unique" de la ficha: su icono (marco morado) muestra la cara del heroe. Si la fila es
# "Grace / Unique", "Commandment / Unique"... el de Unique es el segundo.
ETIQUETA_UNIQUE = (30, 715, 300, 740)
ICONOS_UNIQUE = [(40, 750, 105, 830), (120, 750, 185, 830)]


def recorte_retrato(pantalla):
    """Cara del heroe, del icono de su habilidad Unique."""
    etiqueta = " ".join(ocr.leer_region(pantalla, ETIQUETA_UNIQUE)).lower()
    x1, y1, x2, y2 = ICONOS_UNIQUE[1 if "/" in etiqueta else 0]
    return pantalla[y1:y2, x1:x2].copy()


# ------------------------------------------------------------- lista de Heroes (iconos)
def casilla_vacia(pantalla, x: int, y: int) -> bool:
    """Una casilla con heroe tiene un marco claro arriba. Se busca el punto mas claro de cada columna en
    una franja de 10 px: asi da igual si al bajar la lista la fila quedo unos pixeles corrida (antes se
    miraba una linea de 2 px, caia en el hueco oscuro entre filas y la lista se cortaba a los 33)."""
    franja = cv2.cvtColor(pantalla[max(0, y - 4):y + 6, x + 10:x + 78], cv2.COLOR_BGR2GRAY)
    return float(franja.max(axis=0).mean()) < BORDE_CASILLA


def leer_filas(pantalla, filas, limite: int) -> tuple[list, bool]:
    """Iconos de esas filas, de izquierda a derecha. True si aparecio un hueco vacio (fin de la lista)."""
    iconos = []
    for y in filas:
        if y + LADO_CASILLA > limite:
            break
        for x in COLUMNAS_LISTA:
            if casilla_vacia(pantalla, x, y):
                return iconos, True
            iconos.append(pantalla[y:y + LADO_CASILLA, x:x + LADO_CASILLA].copy())
    return iconos, False


def recorte_fila(pantalla, y: int):
    return pantalla[y:y + LADO_CASILLA, COLUMNAS_LISTA[0] - 5:COLUMNAS_LISTA[-1] + LADO_CASILLA + 5].copy()


def buscar_fila(pantalla, fila) -> int | None:
    """Altura de esa fila en la pantalla (tras bajar la lista), o None si no esta."""
    x0 = COLUMNAS_LISTA[0] - 5
    zona = pantalla[ARRIBA_LISTA:LIMITE_LISTA_FINAL, x0:x0 + fila.shape[1]]
    if zona.shape[0] < fila.shape[0]:
        return None
    _, valor, _, (_, y) = cv2.minMaxLoc(cv2.matchTemplate(zona, fila, cv2.TM_CCOEFF_NORMED))
    return y + ARRIBA_LISTA if valor >= 0.9 else None


SEPIA_WANTED = 0.63  # parte sepia de la casilla: tus heroes <=0.57, carteles WANTED >=0.68 (medido en 377)


def es_wanted(icono) -> bool:
    """Al final de la lista el juego pone carteles "WANTED" en sepia: heroes que no tienes."""
    hsv = cv2.cvtColor(icono, cv2.COLOR_BGR2HSV)
    sepia = (hsv[..., 0] >= 10) & (hsv[..., 0] <= 28) & (hsv[..., 1] > 60)
    return float(sepia.mean()) > SEPIA_WANTED


def atributo_de_casilla(icono) -> str:
    x1, y1, x2, y2 = ICONO_CASILLA
    return atributo_por_color(icono[y1:y2, x1:x2], minimo=40)


def guardar_caras(iconos) -> None:
    """Guarda las caras numeradas en orden y una hoja con todas para revisarlas de un vistazo."""
    CARAS.mkdir(parents=True, exist_ok=True)
    for vieja in CARAS.glob("*.*"):
        vieja.unlink()
    for i, icono in enumerate(iconos, start=1):
        guardar_imagen(CARAS / f"{i:03d}.png", icono)
    if iconos:
        lado, columnas = 66, 10
        celdas = []
        for i, icono in enumerate(iconos, start=1):
            celda = cv2.resize(icono, (lado, lado))
            cv2.putText(celda, str(i), (3, lado - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3)
            cv2.putText(celda, str(i), (3, lado - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
            celdas.append(celda)
        while len(celdas) % columnas:
            celdas.append(np.zeros_like(celdas[0]))
        filas = [np.hstack(celdas[i:i + columnas]) for i in range(0, len(celdas), columnas)]
        guardar_imagen(CARAS / "hoja.jpg", np.vstack(filas))


def cargar_caras() -> list:
    return [img for img in (leer_imagen(r) for r in sorted(CARAS.glob("[0-9][0-9][0-9].png"))) if img is not None]


MISMAS_CARTAS = 10  # diferencia media entre las cartas: mismo heroe ~2, heroes distintos >=27 (medido)


def mismas_cartas(a, b) -> bool:
    if not a or not b or len(a) != len(b):
        return False
    return float(np.mean([np.mean(cv2.absdiff(x, y)) for x, y in zip(a, b)])) < MISMAS_CARTAS


def recorte_carta(pantalla, i: int):
    x1, y1, x2, y2 = juego.FICHA_CARTAS[i]
    return pantalla[y1:y2, x1:x2].copy()


# ------------------------------------------------------------ pasar a la biblioteca
TIPO_ES = {"single": "Un objetivo", "area": "Área", "defensa": "Defensa", "apoyo": "Apoyo", "otro": "Otro"}


def roles_de(h: dict) -> list[str]:
    """Roles del heroe a partir de sus cartas (para armar equipos)."""
    roles = []
    for c in h.get("cartas") or []:
        t = (c.get("texto") or "").lower()
        nuevos = {"single": ["dano_single"], "area": ["dano_area"], "defensa": ["aguante"], "apoyo": ["buff"]}.get(
            c.get("tipo"), [])
        if re.search(r"removes? stances?", t):
            nuevos.append("quita_postura")
        if re.search(r"restores?.{0,40}\bhp\b|recovers?.{0,30}\bhp\b", t):
            nuevos.append("curacion")
        if re.search(r"decreases?.{0,60}enem", t):
            nuevos.append("debuff")
        roles += [r for r in nuevos if r not in roles]
    return roles


def _existente(h: dict, biblioteca: dict, base: dict, capturados: list[dict]) -> str | None:
    """El personaje de la biblioteca que es este heroe, si ya existe.

    1) el que tiene su misma clave del juego; 2) uno "de relleno" de la base (sin cartas, de los
    equipos recomendados) cuyo nombre aparece en el del heroe y del mismo color, pero solo si es el
    unico heroe capturado que encaja (con dos Escanor no se adivina cual es)."""
    for pid, datos in base.items():
        clave = (datos or {}).get("clave", "")
        # misma clave, o mismo nombre y color aunque el titulo se haya leido distinto (sin el color,
        # Thonar rojo y verde se juntaban con Thonar azul)
        mismo_nombre = clave.split("] ")[-1].lower() == h["nombre"].lower() and datos.get("color") == h.get("color")
        if clave and (clave == h["clave"] or mismo_nombre):
            return pid
    for pid, pj in biblioteca.items():
        if pj.cartas or pj.id not in base:
            continue
        palabra = pj.nombre.split("(")[0].split()[0].lower()
        def encaja(otro):
            return re.search(rf"\b{re.escape(palabra)}\b", otro["nombre"].lower()) and \
                pj.color in ("sin definir", otro.get("color"))
        if encaja(h) and sum(1 for otro in capturados if encaja(otro)) == 1:
            return pid
    return None


def pasar_a_biblioteca(catalogo: dict) -> tuple[int, int]:
    """Pasa los heroes capturados a la biblioteca local (pagina Personajes) y los marca como tuyos.

    Los que ya estan (los del guion de Perros...) solo reciben su icono: sus cartas y su retrato no se
    tocan, porque el bot los usa para pelear. Devuelve (nuevos, ya existentes)."""
    import shutil

    from lumen.equipo import recorte_para_plantilla

    biblioteca = P.cargar()
    base = P._leer_yaml(P.BASE)
    capturados = list(catalogo.values())
    nuevos = existentes = 0
    for pid_captura, h in catalogo.items():
        origen = CARPETA / pid_captura
        destino = _existente(h, biblioteca, base, capturados)
        cara = origen / "icono.png" if (origen / "icono.png").is_file() else origen / "retrato_ficha.png"
        tengo = h.get("en_cuenta", True)  # los WANTED de la lista no estan en tu cuenta
        if destino and biblioteca[destino].cartas:
            if cara.is_file() and tengo:  # el cartel WANTED no sustituye a la cara buena
                (P.CARPETA / destino).mkdir(parents=True, exist_ok=True)
                shutil.copyfile(cara, P.CARPETA / destino / f"{P.ICONO}.png")
            if tengo:
                P.marcar_tengo(destino, True)
            existentes += 1
            continue
        pid = destino or pid_captura
        cartas, normales = {}, 0
        carpeta = P.CARPETA / pid
        for i, c in enumerate(h.get("cartas") or [], start=1):
            if c.get("ulti"):
                cid = "ulti"
            else:
                normales += 1
                cid = f"skill_{normales}"
            cartas[cid] = P.CartaPj(cid, f"{TIPO_ES.get(c.get('tipo'), 'Otro')} ({c.get('nombre', '')})")
            crudo = leer_imagen(origen / f"carta_{i}{P.SUFIJO_FICHA}.png")
            if crudo is not None:  # igual que el Editor: sin marco y al tamano de la carta en la mano
                ex, ey = P.ESCALA_FICHA
                plantilla = cv2.resize(recorte_para_plantilla(crudo), None, fx=ex, fy=ey, interpolation=cv2.INTER_AREA)
                guardar_imagen(carpeta / f"{cid}{P.SUFIJO_FICHA}.png", plantilla)
        if cara.is_file():
            carpeta.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cara, carpeta / f"{P.ICONO}.png")
        P.guardar(P.Personaje(id=pid, nombre=h["nombre"], color=h.get("color", "sin definir"),
                              raza=h.get("raza", "sin definir"), roles=roles_de(h), cartas=cartas, tengo=tengo,
                              propio=pid not in base))
        if destino:
            existentes += 1
        else:
            nuevos += 1
    return nuevos, existentes


# ------------------------------------------------------------------ que esta completo
# Las capturas saltan lo completo y repiten lo incompleto: al salir heroes nuevos se capturan solo esos, y lo
# que se leyo mal se puede corregir volviendo a lanzar la captura (pedido del usuario, 2026-10-29).
def ficha_completa(h: dict) -> bool:
    cartas = (h or {}).get("cartas") or []
    return (len(cartas) >= 3 and all(c.get("nombre") and c.get("texto") for c in cartas)
            and (h or {}).get("color", "sin definir") != "sin definir")


def pasivas_completas(h: dict) -> bool:
    return bool((h or {}).get("pasivas_capturadas") and (h or {}).get("pasiva") and not (h or {}).get("pasivas_incompletas"))


def id_por_clave(catalogo: dict, clave: str, atributo: str = "", minimo: float = 0.75) -> str | None:
    """El heroe del catalogo con esa clave ("[titulo] nombre"): exacta o, si el lector de texto la leyo algo
    distinta, la mas parecida (desde 0.75: "Ludociel of Flash)", "Sho Kusakabe"). Con varias, manda el atributo."""
    iguales = [pid for pid, h in catalogo.items() if (h or {}).get("clave") == clave]
    if not iguales:
        puntos = sorted(((difflib.SequenceMatcher(None, clave.lower(), (h or {}).get("clave", "").lower()).ratio(), pid)
                         for pid, h in catalogo.items()), reverse=True)
        mejor = puntos[0][0] if puntos else 0.0
        iguales = [pid for r, pid in puntos if r >= minimo and r >= mejor - 0.02]
    if len(iguales) > 1 and atributo:
        iguales = [pid for pid in iguales if catalogo[pid].get("atributo") == atributo] or iguales
    return iguales[0] if iguales else None


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
        "lista": "Recortando los iconos de la lista",
        "abrir_primero": "Abriendo el primer héroe",
    }

    def __init__(self, valores: dict):
        super().__init__(valores)
        # "caras": solo la fase 1 (lista); "fichas": solo la fase 2, con las caras ya guardadas
        self.fase = valores.get("fase", "fichas")
        self.catalogo = cargar_catalogo()
        self.vistos: set[str] = set()
        self.capturados = 0
        self.saltados = 0
        self.actual: dict | None = None
        self.anterior = None
        self.esperando_desde = time.time()
        self.intentos = 0
        self.ultima_clave = ""  # el heroe recien guardado (tras la flecha puede seguir en pantalla un momento)
        self.ultimas_cartas: list = []  # y el dibujo de sus cartas, por si el OCR lee su nombre de otra forma
        self.repetida = 0
        self.quieta_desde = time.time()
        self.sin_ficha_desde: float | None = None
        self.misma_carta = 0
        self.iconos: list | None = None  # iconos de la lista, en orden (None = se empezo en una ficha)
        self.fichas_vistas = 0  # posicion del heroe actual en la lista
        self.volvi_a_lista = False
        self.sin_leer = 0  # cartas seguidas que no se pudieron leer
        if self.fase == "fichas":
            self.iconos = cargar_caras()

    def estado_inicial(self):
        return "buscar_ficha"

    def estados(self):
        return {
            "buscar_ficha": self.buscar_ficha,
            "leer_ficha": self.leer_ficha,
            "leer_cartas": self.leer_cartas,
            "cerrar": self.cerrar,
            "siguiente": self.siguiente,
            "lista": self.lista,
            "abrir_primero": self.abrir_primero,
        }

    # ------------------------------------------------------------------ utilidades
    def _quieta(self, pantalla, zonas) -> bool:
        """True si esas zonas no cambiaron desde la captura anterior (terminaron las animaciones).

        Si tras ESPERA_MAXIMA_QUIETA siguen moviendose, se da por buena igual (y se avisa)."""
        actual = np.concatenate([pantalla[y1:y2, x1:x2].astype(np.int16).ravel() for x1, y1, x2, y2 in zonas])
        if self.anterior is None or self.anterior.shape != actual.shape:
            self.anterior, self.quieta_desde = actual, time.time()
            return False
        diferencia = float(np.abs(actual - self.anterior).mean())
        self.anterior = actual
        if diferencia < DIFERENCIA_ESTABLE:
            return True
        if time.time() - self.quieta_desde > ESPERA_MAXIMA_QUIETA:
            self.log(f"La pantalla sigue moviéndose (diferencia {diferencia:.1f}); leo igual.", "debug")
            return True
        return False

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
        if LISTA.esta(p, 0.85):
            if self.fase == "caras":
                return "lista"
            # Fase 2: empezar siempre por el primer heroe de la lista (su cara es la 001)
            self.log(f"Abro el primer héroe de la lista ({len(self.iconos)} caras guardadas).", "ok")
            self._subir_lista(o)
            entrada.clic((COLUMNAS_LISTA[0] + LADO_CASILLA // 2, PRIMERA_FILA + LADO_CASILLA // 2), o, espera=1.5)
            self.esperando_desde = time.time()
            return "abrir_primero"
        if FICHA.esta(p, 0.85):
            if not self.volvi_a_lista:
                # Para tener los iconos hay que empezar en la lista: volver a ella con la flecha.
                self.volvi_a_lista = True
                self.log("Estoy en una ficha: vuelvo a la lista de Heroes para empezar desde el principio.")
                entrada.clic(VOLVER, o, espera=2.0)
                return None
            if self.fase == "caras":
                self.log("No reconocí la lista de Heroes. Deja el juego en la lista y vuelve a empezar.", "error")
                raise TerminarModo()
            self.anterior = None
            self.log("No reconocí la lista de Heroes: empiezo desde esta ficha, así que las caras pueden no "
                     "cuadrar (se comprueban con el atributo).", "aviso")
            return "leer_ficha"
        if time.time() - self.esperando_desde > 90:
            self.log("No veo la ficha de ningún héroe. Ábrela en el juego (Heroes -> un héroe) y vuelve a empezar.", "error")
            raise TerminarModo()
        return None

    def _subir_lista(self, o):
        for _ in range(4):
            entrada.arrastrar((275, 300), (275, 690), o, duracion=0.3)
            control.esperar(0.4)
        control.esperar(1.0)

    def lista(self, p, o):
        """Recorta el icono de cada heroe de la lista, en orden, bajando fila a fila hasta el final."""
        self.log("Lista de Heroes: recorto el icono de cada héroe en orden...", "ok")
        self._subir_lista(o)
        p = self.capturar()[0]
        fotos = CARPETA / "lista"
        for vieja in fotos.glob("*.jpg"):
            vieja.unlink()
        guardar_imagen(fotos / "lista_00.jpg", p)
        filas = [PRIMERA_FILA + PASO_FILA * k for k in range(6)]
        iconos, fin = leer_filas(p, filas, LIMITE_LISTA)
        ultima = max(y for y in filas if y + LADO_CASILLA <= LIMITE_LISTA)
        sin_moverse = 0
        while not fin and len(iconos) < 600:
            referencia = recorte_fila(p, ultima)
            anterior = recorte_fila(p, ultima - PASO_FILA)  # por si la ultima queda tapada al deslizar
            inicio = (275, 650 - 50 * sin_moverse)  # si el juego ignora un arrastre, probar desde otra altura
            entrada.arrastrar(inicio, (275, inicio[1] - FILAS_POR_ARRASTRE * PASO_FILA), o, duracion=0.8)
            control.esperar(1.5)  # que termine de deslizarse
            p = self.capturar()[0]
            guardar_imagen(fotos / f"lista_{len(iconos):03d}.jpg", p)
            y = buscar_fila(p, referencia)
            if y is None:
                y_anterior = buscar_fila(p, anterior)
                y = y_anterior + PASO_FILA if y_anterior is not None else None
            if y is None:
                self.log(f"Perdí la cuenta al bajar la lista: me quedo con {len(iconos)} iconos.", "aviso")
                break
            if abs(y - ultima) < 4:
                sin_moverse += 1
                if sin_moverse < 3:  # quiza el juego no hizo caso al arrastre: probar otra vez antes de rendirse
                    self.log("La lista no se movió; lo intento otra vez.", "debug")
                    continue
                # No baja mas: es el final. Leer lo que queda (aunque lo cruce el cartel del juego).
                abajo = [y + PASO_FILA * k for k in range(1, 4)]
                restantes, _ = leer_filas(p, abajo, LIMITE_LISTA_FINAL)
                iconos += restantes
                break
            sin_moverse = 0
            nuevas = [y + PASO_FILA * k for k in range(1, 8) if y + PASO_FILA * k + LADO_CASILLA <= LIMITE_LISTA]
            mas, fin = leer_filas(p, nuevas, LIMITE_LISTA)
            iconos += mas
            ultima = nuevas[-1] if nuevas else y
            control.actividad()
        self.iconos = iconos
        if self.fase == "caras":
            guardar_caras(iconos)
            wanted = sum(1 for i in iconos if es_wanted(i))
            self.log(f"Fase 1 terminada: {len(iconos)} caras ({len(iconos) - wanted} tuyas y {wanted} WANTED, que no "
                     "tienes) en capturas\\heroes\\iconos (mira hoja.jpg). Ahora la fase 2: Capturar fichas.", "ok")
            raise TerminarModo()
        self.log(f"{len(iconos)} iconos recortados. Abro el primer héroe.", "ok")
        self._subir_lista(o)
        entrada.clic((COLUMNAS_LISTA[0] + LADO_CASILLA // 2, PRIMERA_FILA + LADO_CASILLA // 2), o, espera=1.5)
        self.esperando_desde = time.time()
        return "abrir_primero"

    def abrir_primero(self, p, o):
        if FICHA.esta(p, 0.85):
            self.anterior = None
            return "leer_ficha"
        if LISTA.esta(p, 0.85) and time.time() - self.esperando_desde > 5:
            entrada.clic((COLUMNAS_LISTA[0] + LADO_CASILLA // 2, PRIMERA_FILA + LADO_CASILLA // 2), o, espera=1.5)
            self.esperando_desde = time.time()
        return None

    def leer_ficha(self, p, o):
        if not FICHA.esta(p, 0.85):
            # Sin ficha a la vista (cargando, otra ventana encima...). Si dura, volver a buscarla.
            self.sin_ficha_desde = self.sin_ficha_desde or time.time()
            if time.time() - self.sin_ficha_desde > 8:
                self.log("Ya no veo la ficha del héroe. Vuelvo a buscarla.", "aviso")
                self.sin_ficha_desde = None
                self.esperando_desde = time.time()
                return "buscar_ficha"
            return None
        self.sin_ficha_desde = None
        if not self._quieta(p, ZONAS_ESTABLES):
            return None
        pantallas = [p]
        for _ in range(LECTURAS_DATOS - 1):
            control.esperar(0.25)
            pantallas.append(self.capturar()[0])
        titulo, nombre = leer_cabecera_varias(pantallas)
        atributo, raza, caracteristicas = leer_datos_varias(pantallas)
        if not nombre or not atributo:
            self.intentos += 1
            self.log(f"Lectura incompleta (nombre: '{nombre}', atributo: '{atributo}'); reintento.", "debug")
            if self.intentos >= 4:
                self.log("No pude leer el nombre de este héroe: lo salto.", "aviso")
                self.intentos = 0
                guardar_imagen(CARPETA / "sin_leer" / f"{time.strftime('%H%M%S')}.jpg", p)
                self.fichas_vistas += 1  # aunque no se lea, ocupa su sitio en la lista
                return "siguiente"
            return None
        self.intentos = 0
        clave = f"[{titulo}] {nombre}" if titulo else nombre
        recortes = [recorte_carta(p, i) for i in range(len(juego.FICHA_CARTAS))]
        if clave == self.ultima_clave or mismas_cartas(recortes, self.ultimas_cartas):
            # Sigue el heroe anterior: la flecha aun no cambio la ficha (o no funciono). Se compara tambien
            # el dibujo de las cartas: una lectura distinta del nombre lo contaba dos veces y desfasaba
            # todas las caras siguientes ("SBlessing" / "Blessing of the Earth Diane").
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
        existente = id_por_clave(self.catalogo, clave, atributo, minimo=0.9)
        if self.valores.get("solo_nuevos", True) and existente and ficha_completa(self.catalogo[existente]):
            # Ya esta completo: no se vuelven a leer sus cartas (lo lento, ~10 s por heroe)
            self.fichas_vistas += 1
            self.saltados += 1
            self.log(f"{nombre} ya está completo: lo salto.", "debug")
            self.publicar_stats(victorias=self.capturados, saltados=self.saltados)
            return "siguiente"
        color = COLOR.get(atributo.lower().strip(), "sin definir")
        self.actual = {
            "clave": clave, "titulo": titulo, "nombre": nombre, "atributo": atributo, "color": color,
            "raza_juego": raza, "raza": RAZA_ES.get(raza.lower().strip(), "sin definir"),
            "caracteristicas": caracteristicas,
            "cartas": [], "_recortes": recortes,
            "_ficha": p.copy(), "_indice": self.fichas_vistas,
        }
        self.fichas_vistas += 1
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
        if not self._quieta(p, [ZONA_SKILL_INFO]):
            return None
        self.intentos = 0
        carta = leer_skill(p)
        cartas = self.actual["cartas"]
        if carta is not None and cartas and carta["nombre"] == cartas[-1]["nombre"]:
            # La misma que acabo de leer: el popup aun no cambio. Esperar y, si sigue, pulsar otra vez.
            self.misma_carta += 1
            if self.misma_carta in (4, 8):
                entrada.clic(FLECHA_SKILL, o, espera=0.5)
            if self.misma_carta < 12:
                return None
            self.log("Skill Info no pasa a la siguiente carta: sigo con el héroe.", "aviso")
            return self._cartas_listas()
        self.misma_carta = 0
        if carta is None:
            self.sin_leer += 1
            nombre = re.sub(r"\W+", "_", self.actual["nombre"])[:30]
            guardar_imagen(CARPETA / "sin_leer" / f"carta_{nombre}_{len(cartas) + self.sin_leer}.jpg", p)
            self.log("No pude leer esta carta (guardo una foto en capturas\\heroes\\sin_leer); paso a la siguiente.",
                     "aviso")
            if self.sin_leer >= MAX_CARTAS_SIN_LEER:
                self.log(f"No consigo leer las cartas de {self.actual['nombre']}: sigo con el siguiente héroe.", "aviso")
                self.sin_leer = 0
                return self._cartas_listas()
        elif (cartas and carta["nombre"] == cartas[0]["nombre"]) or len(cartas) >= MAX_CARTAS:
            return self._cartas_listas()  # di la vuelta: ya estan todas
        else:
            self.sin_leer = 0
            cartas.append(carta)
            self.log(f"   Carta {len(cartas)}: {carta['nombre']} ({carta['tipo']})", "debug")
        entrada.clic(FLECHA_SKILL, o, espera=0.5)
        self.anterior = None
        return None

    def _cartas_listas(self) -> str:
        """Las cartas van en orden: normales y la ultima es la Ultimate (si tiene 3 o mas)."""
        cartas = self.actual["cartas"]
        for i, carta in enumerate(cartas):
            carta["ulti"] = carta["ulti"] or (len(cartas) >= 3 and i == len(cartas) - 1)
        if len(cartas) < 3:
            self.log(f"Solo leí {len(cartas)} cartas de {self.actual['nombre']}: revísalo.", "aviso")
        return "cerrar"

    def cerrar(self, p, o):
        if SKILL_INFO.esta(p, 0.85):
            self.clic_si(CERRAR, p, o, umbral=0.8, espera=0.5)
            return None
        if self.actual is None:  # Skill Info estaba abierto al empezar: cerrado, a empezar por el principio
            self.anterior = None
            return "buscar_ficha"
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
        self.ultimas_cartas = h.pop("_recortes")
        for i, recorte in enumerate(self.ultimas_cartas, start=1):
            guardar_imagen(carpeta / f"carta_{i}{P.SUFIJO_FICHA}.png", recorte)
        ficha = h.pop("_ficha")
        guardar_imagen(carpeta / "ficha.jpg", ficha)
        guardar_imagen(carpeta / "retrato_ficha.png", recorte_retrato(ficha))
        indice = h.pop("_indice")
        if self.iconos is not None and indice < len(self.iconos):
            icono = self.iconos[indice]
            del_icono = "" if es_wanted(icono) else atributo_de_casilla(icono)  # el cartel no tiene color
            if es_wanted(icono):
                h["en_cuenta"] = False
                self.log(f"{h['nombre']} es un WANTED: no lo tienes en tu cuenta.", "debug")
            if del_icono and del_icono != h["atributo"]:
                # El orden no cuadra (p. ej. la lista cambio): mejor sin icono que con el de otro.
                self.log(f"El icono nº {indice + 1} de la lista es {del_icono} y {h['nombre']} es {h['atributo']}: "
                         "no se lo pongo.", "aviso")
            else:
                guardar_imagen(carpeta / "icono.png", icono)
        h["capturado"] = time.strftime("%Y-%m-%d %H:%M")
        self.catalogo[pid] = h
        # Capturas viejas de este mismo heroe guardadas con su titulo como nombre (antes de leer bien
        # los titulos sin corchetes: "Waves of the Earth" era Queen Diane).
        for otro, datos in list(self.catalogo.items()):
            if otro != pid and h["titulo"] and datos.get("nombre") == h["titulo"] and not datos.get("titulo"):
                del self.catalogo[otro]
                self.log(f"Quité la captura vieja '{h['titulo']}' (era {h['nombre']}).", "debug")
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

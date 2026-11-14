"""Heroes nuevos del juego desde 7dshub.com (datos e imagenes con permiso de su dueno, 2026-11-08), solos y para todos.

Calendario del juego (el usuario, 2026-11-13): actualizacion los miercoles de madrugada y heroe nuevo un jueves de
cada dos (el otro jueves es de descanso). El Lumen del administrador revisa el jueves que toca (ultimo estreno + 14
dias); si 7dshub aun no lo subio, vuelve a mirar una vez al dia hasta que salga. Asi no se visita la pagina mas de la
cuenta. Si hay un banner corto, el administrador pulsa "Buscar héroes nuevos" y se revisa en el momento.

Lo que se publica de cada heroe nuevo, igual que los 380 que ya vinieron de 7dshub:
- lumen/datos/personajes.yaml (su registro), fuente_7dshub.yaml (su id en 7dshub), fichas.yaml (la ficha de la pagina
  Personajes) y habilidades.yaml (el texto de sus cartas, para que la IA sepa que hacen).
- assets/personajes/<id>/icono_hub.png y <carta>_hub.png (sus cartas recortadas como en la mano: el bot las reconoce
  en pelea desde el primer dia).
"""

import json
import re
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import cv2
import numpy as np
import yaml

from lumen.archivos import escribir_texto
from lumen.rutas import LOGS

API = "https://7dshub.com/api/hero"
CDN = "https://cdn.7dshub.com/images"
AGENTE = "LumenFarm"
CICLO_DIAS = 14  # un heroe nuevo cada dos jueves
ESTADO = LOGS / "heroes_7dshub.json"
COLOR = {1: "rojo", 2: "verde", 3: "azul", 4: "claro", 5: "oscuro", 6: "claro"}
LISTAS = {"skill_1": "skillsA", "skill_2": "skillsB", "ulti": "skillsSpecial"}
ANCHO_CARTA, RECORTE_CARTA = 63, (9, 13, 45, 74)  # como lumen/personajes.py (SUFIJO_HUB): 63 px de ancho, x, y, w, h

PERSONAJES = Path("lumen") / "datos" / "personajes.yaml"
FUENTE = Path("lumen") / "datos" / "fuente_7dshub.yaml"
FICHAS = Path("lumen") / "datos" / "fichas.yaml"
HABILIDADES = Path("lumen") / "datos" / "habilidades.yaml"
IMAGENES = Path("assets") / "personajes"
RUTAS_REPO = (PERSONAJES, FUENTE, FICHAS, HABILIDADES, IMAGENES)

CABEZA_FUENTE = ("# Cada heroe de Lumen y su id en 7dshub.com (https://7dshub.com/hero/<id>). Datos e imagenes de 7dshub,\n"
                 "# con permiso de su dueno (2026-11-08).\n")
CABEZA_HABILIDADES = ("# Texto exacto de cada habilidad (nombre en minusculas -> texto), de 7dshub.com con permiso de su dueno\n"
                      "# (2026-11-08). Lo usa lumen/ia/decidir.py para saber que hace cada carta.\n")


# ------------------------------------------------------------------ internet
def bajar(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    datos = urllib.request.urlopen(req, timeout=30).read()
    time.sleep(0.3)  # sin prisa: es la pagina de otra persona
    return datos


def lista_heroes(bajar=bajar) -> list[dict]:
    return json.loads(bajar(f"{API}?lang=en"))


def detalle(hid: int, bajar=bajar) -> dict:
    return json.loads(bajar(f"{API}/{hid}?lang=en"))


# ------------------------------------------------------------------ calendario
def leer_estado(archivo: Path = ESTADO) -> dict:
    try:
        return json.loads(archivo.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}


def guardar_estado(estado: dict, archivo: Path = ESTADO) -> None:
    archivo.parent.mkdir(parents=True, exist_ok=True)
    escribir_texto(archivo, json.dumps(estado, ensure_ascii=False, indent=1))


def _fecha(texto) -> date | None:
    try:
        return datetime.fromisoformat(str(texto)[:10]).date()
    except (TypeError, ValueError):
        return None


def proxima_revision(estado: dict) -> date | None:
    """El jueves del siguiente heroe (ultimo estreno + 14 dias). None: nunca se reviso, toca ya."""
    ultimo = _fecha(estado.get("ultimo_estreno"))
    return date.fromordinal(ultimo.toordinal() + CICLO_DIAS) if ultimo else None


def toca_revisar(hoy: date, estado: dict) -> bool:
    """Como mucho una vez al dia, y solo desde el jueves que toca (hasta que 7dshub tenga el heroe)."""
    if estado.get("revisado") == hoy.isoformat():
        return False
    prox = proxima_revision(estado)
    return prox is None or hoy >= prox


def estrenado(h: dict, hoy: date) -> date | None:
    """Fecha de salida en el servidor global, si ya salio (7dshub a veces trae heroes que aun no llegan)."""
    salida = _fecha((h.get("release") or {}).get("gb"))
    return salida if salida and salida <= hoy else None


def ultimo_estreno(lista: list[dict], hoy: date) -> date | None:
    fechas = [f for f in (estrenado(h, hoy) for h in lista) if f]
    return max(fechas) if fechas else None


def faltan(lista: list[dict], fuente: dict, hoy: date) -> list[dict]:
    """Los heroes ya estrenados que Lumen aun no tiene."""
    usados = set((fuente or {}).values())
    return [h for h in lista if h.get("id") not in usados and estrenado(h, hoy)]


# ------------------------------------------------------------------ textos (como los 380 que ya vinieron)
def _sin_negrita(texto: str) -> str:
    return re.sub(r"\[/?[bi]\]", "", texto or "").replace("\\n", "\n").replace("※", "").strip()


def nombre(texto: str) -> str:
    return _sin_negrita(texto).strip('"').strip()


def texto_plano(texto: str) -> str:
    texto = re.sub(r"\[[0-9A-Fa-f]{6}\]|\[-\]|\[/?[bi]\]", "", texto or "")
    texto = texto.replace("\\n", " ").replace("\n", " ").replace("※", "")
    return re.sub(r"\s+", " ", texto).replace(" .", ".").strip()


def tipo(texto: str) -> str:
    t = texto.lower()
    if "all enemies" in t:
        return "Área"
    if re.search(r"\b(one|an|a single) enemy\b", t):
        return "Un objetivo"
    return "Apoyo"


def id_lumen(h: dict, ocupados) -> str:
    color = COLOR.get(h.get("attribute"), "rojo")
    base = re.sub(r"[^a-z0-9]+", "_", nombre(h.get("name", "")).lower()).strip("_") + f"_{color}"
    pid, n = base, 2
    while pid in ocupados:
        pid, n = f"{base}_{n}", n + 1
    return pid


def registro(h: dict, d: dict) -> dict:
    cartas = {}
    for carta, lista in LISTAS.items():
        if d.get(lista):
            skill = d[lista][0]
            cartas[carta] = {"descripcion": f"{tipo(texto_plano(skill.get('explain', '')))} ({nombre(skill['name'])})"}
    titulo = nombre(h.get("nickname", ""))
    reg = {"clave": f"{titulo} {nombre(h.get('name', ''))}".strip(), "nombre": nombre(h.get("name", "")),
           "color": COLOR.get(h.get("attribute"), "rojo"), "raza": "desconocida", "roles": [], "cartas": cartas}
    salida = _fecha((h.get("release") or {}).get("gb"))
    if salida:
        reg["estreno"] = salida.isoformat()  # sale en Inicio hasta que cada jugador diga si lo tiene
    return reg


def ficha(d: dict) -> dict:
    f = {}
    for carta, lista in (("skill_1", "skillsA"), ("skill_2", "skillsB")):
        if d.get(lista):
            f[carta] = {"nombre": nombre(d[lista][0]["name"]),
                        "rangos": [_sin_negrita(s.get("explain", "")) for s in d[lista]]}
    if d.get("skillsSpecial"):
        u = d["skillsSpecial"]
        f["ulti"] = {"nombre": nombre(u[0]["name"]), "texto": _sin_negrita(u[-1].get("explain", ""))}
    for clave, campo in (("pasiva", "passive"), ("talento", "ability")):
        if d.get(campo) and d[campo].get("indexes"):
            f[clave] = {"nombre": nombre(d[campo]["name"]), "texto": _sin_negrita(d[campo]["indexes"][-1]["explain"])}
    if d.get("crafts"):
        c = d["crafts"][0]
        f["reliquia"] = {"nombre": nombre(c.get("name", "")), "texto": _sin_negrita((c.get("passive") or {}).get("explain", ""))}
    perfil = {k: v for k, v in (("edad", d.get("age")), ("altura", d.get("height")), ("peso", d.get("weight")),
                                ("cumpleanos", d.get("birth")), ("sangre", d.get("blood")), ("voz", d.get("voice")))
              if v and v != "Unknown"}
    if perfil:
        f["perfil"] = perfil
    return f


def recortar_carta(png: bytes) -> np.ndarray | None:
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    if img is None or not img.size:
        return None
    alto = round(ANCHO_CARTA * img.shape[0] / img.shape[1])
    x, y, w, h = RECORTE_CARTA
    recorte = cv2.resize(img, (ANCHO_CARTA, alto), interpolation=cv2.INTER_AREA)[y:y + h, x:x + w]
    return recorte if recorte.shape[:2] == (h, w) else None


# ------------------------------------------------------------------ escribir en la copia del repo
def preparar(copia: Path, nuevos: list[dict], hoy: date, bajar=bajar) -> list[str]:
    """Agrega a la copia de la rama los heroes que aun le falten. Devuelve los nombres agregados."""
    fuente = yaml.safe_load((copia / FUENTE).read_text(encoding="utf-8")) or {}
    texto_pj = (copia / PERSONAJES).read_text(encoding="utf-8")
    base = yaml.safe_load(texto_pj) or {}
    texto_fichas = (copia / FICHAS).read_text(encoding="utf-8")
    habilidades = yaml.safe_load((copia / HABILIDADES).read_text(encoding="utf-8")) or {}
    hechos = []
    for h in faltan(nuevos, fuente, hoy):  # otra vez contra la rama: quiza otro PC ya lo publico
        d = detalle(h["id"], bajar)
        pid = id_lumen(h, set(base) | set(fuente))
        reg = registro(h, d)
        carpeta = copia / IMAGENES / pid
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / "icono_hub.png").write_bytes(bajar(f"{CDN}/item/{h['id']}.png"))
        for carta, lista in LISTAS.items():
            if not d.get(lista):
                continue
            skill = d[lista][0]
            explicacion = texto_plano(skill.get("explain", ""))
            if explicacion:
                habilidades.setdefault(nombre(skill["name"]).lower(), explicacion)
            recorte = recortar_carta(bajar(f"{CDN}/skill/{skill['id']}.png"))
            if recorte is not None:
                cv2.imwrite(str(carpeta / f"{carta}_hub.png"), recorte)
        texto_pj = texto_pj.rstrip("\n") + "\n" + yaml.safe_dump({pid: reg}, allow_unicode=True, sort_keys=False, width=110)
        texto_fichas = texto_fichas.rstrip("\n") + "\n" + yaml.safe_dump({pid: ficha(d)}, allow_unicode=True,
                                                                          sort_keys=False, width=200)
        base[pid], fuente[pid] = reg, h["id"]
        hechos.append(reg["clave"])
    if not hechos:
        return []
    for archivo, texto in ((PERSONAJES, texto_pj), (FICHAS, texto_fichas)):
        yaml.safe_load(texto)  # tiene que leerse bien antes de publicarlo
        (copia / archivo).write_text(texto, encoding="utf-8", newline="\n")
    (copia / FUENTE).write_text(CABEZA_FUENTE + yaml.safe_dump(dict(sorted(fuente.items())), sort_keys=False),
                                encoding="utf-8", newline="\n")
    (copia / HABILIDADES).write_text(
        CABEZA_HABILIDADES + yaml.safe_dump(dict(sorted(habilidades.items())), allow_unicode=True, sort_keys=False,
                                            width=120), encoding="utf-8", newline="\n")
    return hechos


# ------------------------------------------------------------------ todo junto
@dataclass
class Resultado:
    nuevos: list[str] = field(default_factory=list)  # "[titulo] nombre" de los publicados
    revisado: bool = False  # se miro 7dshub (False: no tocaba)
    proxima: date | None = None


def revisar(raiz: Path, subir, hoy: date | None = None, forzar: bool = False, bajar=bajar,
            archivo_estado: Path = ESTADO) -> Resultado:
    """Mira 7dshub si toca (o si ``forzar``) y publica los heroes que falten con ``subir(preparar_en_copia)``.

    ``subir`` recibe una funcion copia -> lista de nombres y devuelve esa lista (lumen.publicar.subir_heroes_7dshub).
    Lanza la excepcion si no hay internet o git falla: se reintenta otro dia.
    """
    hoy = hoy or date.today()
    estado = leer_estado(archivo_estado)
    if not forzar and not toca_revisar(hoy, estado):
        return Resultado(proxima=proxima_revision(estado))
    lista = lista_heroes(bajar)
    fuente = yaml.safe_load((raiz / FUENTE).read_text(encoding="utf-8")) or {}
    nuevos = faltan(lista, fuente, hoy)
    estado["revisado"] = hoy.isoformat()  # aunque falle git, a 7dshub no se vuelve hasta manana (o con el boton)
    guardar_estado(estado, archivo_estado)
    publicados = subir(lambda copia: preparar(copia, nuevos, hoy, bajar)) if nuevos else []
    ultimo = ultimo_estreno(lista, hoy)
    if ultimo:
        estado["ultimo_estreno"] = ultimo.isoformat()
    guardar_estado(estado, archivo_estado)
    return Resultado(nuevos=list(publicados or []), revisado=True, proxima=proxima_revision(estado))

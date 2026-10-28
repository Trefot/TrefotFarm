"""Lectura del botin en la pantalla de recompensas (Victory): que objetos salieron, cuantos y el oro.

- Las casillas siguen una cuadricula fija (medida con capturas reales): columnas cada 81 px desde
  x=85 y filas en y=405 (una fila), 362/449 (dos) o 319/406/493 (tres). Se detectan las que se
  puedan por su borde y con eso se sabe cuantas filas hay; luego se revisa cada casilla.
- Que objeto es: se compara la parte de arriba del icono (sin el numero ni el cartel "Guaranteed")
  con el catalogo de objetos que se va aprendiendo. Un icono nuevo se guarda como "sin nombre" y
  el usuario le pone nombre una sola vez en la pagina Recompensas.
- Cantidad: los digitos blancos de la esquina inferior derecha (si no hay, es 1).
- Oro: los digitos amarillos junto a la moneda.
Los digitos se comparan con assets/digitos (dibujados con fuentes con remate parecidas a la del juego).

Catalogo de objetos en dos capas, como los personajes: la base (lumen/datos/objetos.yaml y
assets/objetos/, la publica el administrador con los nombres puestos) y la local de cada jugador
(recompensas/objetos/), que se mezcla encima. Un objeto puede estar "unido" a otro (era el mismo,
leido raro: cuenta como el otro) o "descartado" (no era un objeto: p. ej. un cofre a medio abrir).

Galeria: los objetos del inventario del juego con su nombre, tipo y descripcion (los captura el admin
con lumen/modos/captura_objetos.py; base en lumen/datos/galeria_objetos.yaml + assets/objetos/<id>_ficha.png,
local en capturas/objetos/). Un objeto del botin que se parece a uno de la galeria toma su nombre solo.
"""

import threading
from pathlib import Path

import cv2
import numpy as np
import yaml

from lumen.rutas import ASSETS, RAIZ
from lumen.vision import guardar_imagen, leer_imagen

COLUMNAS_X = [85 + 81 * i for i in range(5)]
FILAS_Y = {1: [405], 2: [362, 449], 3: [319, 406, 493]}
LADO = 63
ZONA_ORO = (85, 540, 175, 572)  # x1, y1, x2, y2: "24,000" a la derecha de la moneda
UMBRAL_OBJETO = 0.88  # parecido minimo de forma para decir que dos iconos son el mismo objeto
DIF_COLOR_MAX = 18.0  # y diferencia maxima de color medio (cubo azul y cubo gris: misma forma)

CARPETA = RAIZ / "recompensas" / "objetos"
CATALOGO = CARPETA / "catalogo.yaml"
CARPETA_BASE = ASSETS / "objetos"
CATALOGO_BASE = Path(__file__).resolve().parent / "datos" / "objetos.yaml"
_lock = threading.RLock()

CARPETA_GALERIA = RAIZ / "capturas" / "objetos"
GALERIA = CARPETA_GALERIA / "galeria.yaml"
GALERIA_BASE = Path(__file__).resolve().parent / "datos" / "galeria_objetos.yaml"
# Icono de la ficha del inventario (86 px) reducido a 63 px frente al icono del botin: el mismo objeto
# da 0.97 y los demas <=0.33 (medido con el orbe de Skoll y Hati y los 7 objetos del botin). Pero los
# cubos de esencia tienen la misma forma y solo cambia el color (cubo gris frente a Blue Magic Essence:
# forma 0.89, color 53): tambien se exige color parecido (DIF_COLOR_MAX; mismo objeto: 0.8-3.5).
LADO_FICHA = LADO
UMBRAL_GALERIA = 0.85

# Pantalla quieta: entre dos capturas seguidas con el OK ya visible, la zona del botin cambia 1-4
# (fondo animado) si esta quieta y 10-22 si aun se abren cofres o llegan casillas (medido en peleas reales).
ZONA_BOTIN = (280, 600)
DIF_QUIETA = 5.0


def quieta(anterior, actual) -> bool:
    """True si la pantalla de recompensas ya no se mueve (para no fotografiar cofres a medio abrir)."""
    y1, y2 = ZONA_BOTIN
    if anterior is None or anterior.shape != actual.shape:
        return False
    if float(cv2.absdiff(anterior[y1:y2], actual[y1:y2]).mean()) >= DIF_QUIETA:
        return False
    return len(casillas(anterior)) == len(casillas(actual))


# ------------------------------------------------------------------ casillas
def _cajas_por_borde(pantalla) -> list[tuple[int, int]]:
    zona = pantalla[280:540]
    bordes = cv2.dilate(cv2.Canny(cv2.cvtColor(zona, cv2.COLOR_BGR2GRAY), 60, 160), np.ones((2, 2), np.uint8))
    contornos, _ = cv2.findContours(bordes, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    cajas = []
    for c in contornos:
        x, y, w, h = cv2.boundingRect(c)
        if 54 <= w <= 68 and 54 <= h <= 68 and abs(w - h) <= 6:
            cajas.append((x, y + 280))
    return cajas


def _hay_objeto(celda) -> bool:
    """Una casilla con objeto tiene marco y dibujo brillantes; el fondo detras esta oscuro."""
    v = cv2.cvtColor(celda, cv2.COLOR_BGR2HSV)[..., 2]
    return float(v.mean()) > 95 and float(v.std()) > 25


def casillas(pantalla) -> list[tuple[int, int]]:
    """Esquinas (x, y) de las casillas con objeto, en orden de lectura."""
    detectadas = _cajas_por_borde(pantalla)
    if detectadas:
        y_arriba = min(y for _, y in detectadas)
        filas = min(FILAS_Y, key=lambda n: abs(FILAS_Y[n][0] - y_arriba))
        candidatas = {n: FILAS_Y[n] for n in (filas,)}
    else:  # sin bordes claros: probar las tres disposiciones y quedarse con la que mas objetos ve
        candidatas = FILAS_Y
    mejor = []
    for ys in candidatas.values():
        encontradas = [(x, y) for y in ys for x in COLUMNAS_X if _hay_objeto(pantalla[y : y + LADO, x : x + LADO])]
        if len(encontradas) > len(mejor):
            mejor = encontradas
    return mejor


# ------------------------------------------------------------------ digitos
_digitos: list[tuple[str, np.ndarray]] | None = None
TAM_DIGITO = (10, 14)


def _normalizar(mascara) -> np.ndarray:
    v = cv2.resize(mascara.astype(np.float32), TAM_DIGITO, interpolation=cv2.INTER_AREA).flatten()
    return (v - v.mean()) / (v.std() + 1e-6)


def _referencias():
    global _digitos
    if _digitos is None:
        _digitos = [(f.name[0], _normalizar(leer_imagen(f)[..., 0] > 128)) for f in sorted((ASSETS / "digitos").glob("*.png"))]
    return _digitos


def _clasificar(mascara) -> str:
    v = _normalizar(mascara)
    return max(_referencias(), key=lambda r: float((v * r[1]).mean()))[0]


def _componentes(mascara, alto_min: int, alto_max: int):
    n, etiquetas, stats, _ = cv2.connectedComponentsWithStats(mascara.astype(np.uint8), connectivity=8)
    comps = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if alto_min <= h <= alto_max and 2 <= w <= 14 and area >= 10:
            comps.append((x, y, w, h, etiquetas[y : y + h, x : x + w] == i))
    return sorted(comps, key=lambda c: c[0])


def _grupo_derecho(comps, ancho: int, hueco: int = 3):
    """Los digitos de un numero van juntos, pegados al borde derecho, con la misma altura y
    alineados abajo; lo que no cumple eso es parte del dibujo (p. ej. una arista del cubo)."""
    grupo = []
    for c in reversed(comps):
        x, y, w, h, _ = c
        if not grupo:
            if ancho - (x + w) <= 8:
                grupo.append(c)
            continue
        ref_x, ref_y, _, ref_h, _ = grupo[0]
        if ref_x - (x + w) <= hueco and abs(h - ref_h) <= 2 and abs((y + h) - (ref_y + ref_h)) <= 2:
            grupo.insert(0, c)
        else:
            break
    return grupo


def leer_cantidad(celda) -> int:
    esquina = celda[36:62, 30:LADO]
    hsv = cv2.cvtColor(esquina, cv2.COLOR_BGR2HSV)
    blanco = (hsv[..., 2] >= 185) & (hsv[..., 1] <= 80)
    grupo = _grupo_derecho(_componentes(blanco, 8, 20), esquina.shape[1])
    texto = "".join(_clasificar(m) for *_, m in grupo)
    return int(texto) if texto.isdigit() and int(texto) > 0 else 1


def leer_oro(pantalla) -> int | None:
    x1, y1, x2, y2 = ZONA_ORO
    hsv = cv2.cvtColor(pantalla[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    brillante = hsv[..., 2] >= 150
    texto = "".join(_clasificar(m) for *_, m in _componentes(brillante, 10, 22))  # la coma es baja: se ignora
    return int(texto) if texto.isdigit() else None


# ------------------------------------------------------------------ catalogo de objetos
def icono(celda) -> np.ndarray:
    """Parte de arriba del icono: sin el numero de cantidad ni el cartel 'Guaranteed Reward'."""
    return celda[5:40, 5:LADO - 5].copy()


def _leer_yaml(ruta: Path) -> dict:
    if not ruta.is_file():
        return {}
    with ruta.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def cargar_catalogo() -> dict[str, dict]:
    """La base con lo local encima. Las entradas de la base llevan '_base' (no se guardan en local)."""
    with _lock:
        catalogo = {oid: {**(datos or {}), "_base": True} for oid, datos in _leer_yaml(CATALOGO_BASE).items()}
        for oid, datos in _leer_yaml(CATALOGO).items():
            catalogo[oid] = {**catalogo.get(oid, {}), **(datos or {})}
        return catalogo


def guardar_catalogo(catalogo: dict) -> None:
    """Guarda en local solo lo que no esta igual en la base."""
    with _lock:
        base = _leer_yaml(CATALOGO_BASE)
        local = {}
        for oid, datos in catalogo.items():
            propio = {k: v for k, v in (datos or {}).items() if not k.startswith("_")}
            if base.get(oid) != propio:
                local[oid] = propio
        CARPETA.mkdir(parents=True, exist_ok=True)
        CATALOGO.write_text(yaml.safe_dump(local, allow_unicode=True, sort_keys=False), encoding="utf-8")


def ruta_icono(oid: str) -> Path:
    local = CARPETA / f"{oid}.png"
    return local if local.is_file() else CARPETA_BASE / f"{oid}.png"


def destino(oid: str, catalogo: dict) -> str | None:
    """El objeto que cuenta de verdad: sigue las uniones; None si se descarto."""
    vistos = set()
    while oid and oid not in vistos:
        vistos.add(oid)
        datos = catalogo.get(oid) or {}
        if datos.get("descartado"):
            return None
        if not datos.get("unido_a"):
            return oid
        oid = datos["unido_a"]
    return oid


def visibles(catalogo: dict) -> list[str]:
    """Objetos que se muestran (sin los unidos a otro ni los descartados)."""
    return [oid for oid, d in catalogo.items() if not (d or {}).get("unido_a") and not (d or {}).get("descartado")]


# ------------------------------------------------------------------ galeria del inventario
def cargar_galeria_local() -> dict[str, dict]:
    return _leer_yaml(GALERIA)


def guardar_galeria_local(galeria: dict) -> None:
    with _lock:
        CARPETA_GALERIA.mkdir(parents=True, exist_ok=True)
        GALERIA.write_text(yaml.safe_dump(galeria, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")


def cargar_galeria() -> dict[str, dict]:
    """La galeria publicada con la capturada en esta PC encima (de cada texto, la lectura mas completa)."""
    galeria = {gid: dict(g or {}) for gid, g in _leer_yaml(GALERIA_BASE).items()}
    for gid, g in cargar_galeria_local().items():
        previo = galeria.get(gid, {})
        galeria[gid] = {**previo, **(g or {})}
        for campo in ("tipo", "descripcion"):
            galeria[gid][campo] = max((previo.get(campo) or "", (g or {}).get(campo) or ""), key=len)
    return galeria


def ruta_ficha(gid: str) -> Path:
    local = CARPETA_GALERIA / f"{gid}_ficha.png"
    return local if local.is_file() else CARPETA_BASE / f"{gid}_ficha.png"


def guardar_ficha(gid: str, icono_ficha) -> None:
    guardar_imagen(CARPETA_GALERIA / f"{gid}_ficha.png", icono_ficha)


def _icono_de_ficha(gid: str):
    """El icono de la galeria como se ve en el botin (63 px, parte de arriba)."""
    img = leer_imagen(ruta_ficha(gid))
    if img is None:
        return None
    return icono(cv2.resize(img, (LADO_FICHA, LADO_FICHA), interpolation=cv2.INTER_AREA))


_cache_galeria: dict[str, object] = {}


def en_galeria(img_icono, galeria: dict) -> str | None:
    """El objeto de la galeria con ese icono (o None)."""
    mejor, mejor_valor = None, UMBRAL_GALERIA
    for gid in galeria:
        if gid not in _cache_galeria:
            _cache_galeria[gid] = _icono_de_ficha(gid)
        ref = _cache_galeria[gid]
        if ref is None or ref.shape != img_icono.shape:
            continue
        valor = float(cv2.matchTemplate(img_icono, ref, cv2.TM_CCOEFF_NORMED).max())
        dif_color = float(np.abs(img_icono.reshape(-1, 3).mean(0) - ref.reshape(-1, 3).mean(0)).max())
        if valor >= mejor_valor and dif_color <= DIF_COLOR_MAX:
            mejor, mejor_valor = gid, valor
    return mejor


def _datos_galeria(g: dict) -> dict:
    return {k: g[k] for k in ("nombre", "tipo", "descripcion") if g.get(k)}


def vincular_galeria() -> int:
    """Pone nombre, tipo y descripcion de la galeria a los objetos del botin que se le parecen.
    El nombre que ya les puso el jugador se respeta. Devuelve cuantos vinculo."""
    with _lock:
        galeria = cargar_galeria()
        if not galeria:
            return 0
        catalogo = cargar_catalogo()
        hechos = 0
        for oid in visibles(catalogo):
            datos = catalogo[oid]
            img = leer_imagen(ruta_icono(oid))
            if datos.get("galeria"):
                # Vinculos de antes de exigir el color (v3.6.4 llamo "Blue Magic Essence" al cubo gris): deshacer.
                gid_viejo = datos["galeria"]
                if img is not None and gid_viejo in galeria and en_galeria(img, {gid_viejo: galeria[gid_viejo]}) is None:
                    for campo, valor in _datos_galeria(galeria[gid_viejo]).items():
                        if datos.get(campo) == valor:
                            datos[campo] = "" if campo == "nombre" else None
                    datos.pop("galeria", None)
                    for campo in ("tipo", "descripcion"):
                        if datos.get(campo) is None:
                            datos.pop(campo, None)
                    hechos += 1
                elif gid_viejo in galeria:
                    # Vinculo bueno: si la galeria tiene ahora un texto mas completo, se actualiza ("Enha...").
                    for campo in ("tipo", "descripcion"):
                        nuevo = galeria[gid_viejo].get(campo) or ""
                        if len(nuevo) > len(datos.get(campo) or ""):
                            datos[campo] = nuevo
                            hechos += 1
                continue
            gid = en_galeria(img, galeria) if img is not None else None
            if gid:
                nombre_propio = datos.get("nombre")
                datos.update(_datos_galeria(galeria[gid]), galeria=gid)
                if nombre_propio:
                    datos["nombre"] = nombre_propio
                hechos += 1
        if hechos:
            guardar_catalogo(catalogo)
        return hechos


def identificar(img_icono, catalogo: dict) -> str | None:
    """Id del objeto; si no se parece a ninguno conocido, se agrega al catalogo como 'sin nombre'.
    None si se parece a uno descartado (no es un objeto)."""
    mejor, mejor_valor = None, UMBRAL_OBJETO
    for oid in catalogo:
        ref = leer_imagen(ruta_icono(oid))
        if ref is None or ref.shape != img_icono.shape:
            continue
        valor = float(cv2.matchTemplate(img_icono, ref, cv2.TM_CCOEFF_NORMED).max())
        dif_color = float(np.abs(img_icono.reshape(-1, 3).mean(0) - ref.reshape(-1, 3).mean(0)).max())
        if valor >= mejor_valor and dif_color <= DIF_COLOR_MAX:
            mejor, mejor_valor = oid, valor
    if mejor:
        return destino(mejor, catalogo)
    galeria = cargar_galeria()
    gid = en_galeria(img_icono, galeria) if galeria else None
    n = 1
    while f"objeto_{n}" in catalogo:
        n += 1
    oid = f"objeto_{n}"
    # Si esta en la galeria del inventario, entra ya con su nombre y descripcion.
    catalogo[oid] = {"nombre": "", **(_datos_galeria(galeria[gid]) if gid else {}), **({"galeria": gid} if gid else {})}
    guardar_imagen(CARPETA / f"{oid}.png", img_icono)
    return oid


def analizar(pantalla) -> dict:
    """{'objetos': {id: cantidad}, 'oro': int | None}. Agrega al catalogo los objetos nuevos."""
    with _lock:
        catalogo = cargar_catalogo()
        objetos: dict[str, int] = {}
        for x, y in casillas(pantalla):
            celda = pantalla[y : y + LADO, x : x + LADO]
            oid = identificar(icono(celda), catalogo)
            if oid is None:  # descartado: no es un objeto
                continue
            objetos[oid] = objetos.get(oid, 0) + leer_cantidad(celda)
        guardar_catalogo(catalogo)
        return {"objetos": objetos, "oro": leer_oro(pantalla)}


def nombre(oid: str, catalogo: dict | None = None) -> str:
    catalogo = catalogo if catalogo is not None else cargar_catalogo()
    oid = destino(oid, catalogo) or oid
    return (catalogo.get(oid) or {}).get("nombre") or f"Sin nombre ({oid.split('_')[-1]})"

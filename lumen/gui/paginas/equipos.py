"""Pagina Equipos: equipos recomendados por cada contenido, del mejor al mas dificil.

Los equipos vienen de lumen/datos/equipos.yaml (base fija que mantiene el administrador) y, en el
modo administrador, de personajes/equipos.yaml (los que el admin crea aqui, antes de publicarlos).
Cada equipo es una tarjeta desplegable: retratos (en gris los que no tienes), nivel, si el bot lo
juega, que te falta, como se juega y, si el bot ya jugo con el, lo que se midio. Los equipos medidos
(en esta PC o en las pruebas, campo "minutos" de equipos.yaml) van primero, del mas rapido al mas lento;
el primero es el que sale en Inicio.
"""

import re
from pathlib import Path

import yaml
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QCompleter,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from lumen import config, historial
from lumen import personajes as P
from lumen.gui import iconos, tema
from lumen.gui.comun import Pagina
from lumen.gui.paginas.personajes import _en_gris
from lumen.modos import MODOS
from lumen.modos.catalogo import CATALOGO, contenido_de

ARCHIVO = Path(__file__).resolve().parents[2] / "datos" / "equipos.yaml"
NIVELES = {
    "recomendado": ("Recomendado", tema.OK),
    "bueno": ("Bueno", "#4f8fe0"),
    "alternativa": ("Alternativa", tema.AVISO),
}


PROPIOS = P.CARPETA / "equipos.yaml"  # equipos que crea el admin (fuera de git hasta publicarlos)
MIN_PELEAS = 5  # peleas medidas para fiarse de las cifras y ordenar por ellas


def _leer(ruta: Path) -> dict:
    if not ruta.is_file():
        return {}
    with ruta.open(encoding="utf-8") as f:
        return yaml.load(f, Loader=P.CARGADOR_YAML) or {}


def cargar_equipos() -> dict:
    """La base y, detras de los de cada contenido, los del admin (marcados con 'propio'). Un equipo del admin
    que ya esta en la base (ya publicado: los mismos personajes) no se repite."""
    equipos = _leer(ARCHIVO)
    for clave, lista in _leer(PROPIOS).items():
        en_base = {frozenset(d.get("personajes") or []) for d in equipos.get(clave, []) if isinstance(d, dict)}
        for i, datos in enumerate(lista or []):
            if frozenset(datos.get("personajes") or []) in en_base:
                continue
            equipos.setdefault(clave, []).append({**datos, "propio": True, "_indice": i})
    return equipos


def _mismo_nombre(a: str, b: str) -> bool:
    return bool(a) and re.sub(r"\W", "", a.lower()) == re.sub(r"\W", "", b.lower())


def guardar_propio(clave: str, datos: dict, anterior: tuple[str, int] | None = None) -> None:
    """Crea un equipo del admin o reemplaza uno suyo (``anterior`` = (clave, indice))."""
    propios = _leer(PROPIOS)
    if anterior:
        vieja, indice = anterior
        propios.get(vieja, []).pop(indice)
        if not propios.get(vieja):
            propios.pop(vieja, None)
    propios.setdefault(clave, []).append(datos)
    PROPIOS.parent.mkdir(parents=True, exist_ok=True)
    PROPIOS.write_text(yaml.safe_dump(propios, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")


def borrar_propio(clave: str, indice: int) -> None:
    propios = _leer(PROPIOS)
    propios.get(clave, []).pop(indice)
    if not propios.get(clave):
        propios.pop(clave, None)
    PROPIOS.write_text(yaml.safe_dump(propios, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")


def medidas(clave: str) -> dict[frozenset, dict]:
    """Lo que el bot midio con cada equipo en este contenido (de logs/historial.jsonl)."""
    equipo = getattr(MODOS.get(clave), "equipo", None)  # el que jugaban las sesiones viejas, sin equipo guardado
    return historial.por_equipo(historial.leer(limite=1_000_000), clave, equipo.orden if equipo else ())


def _peleas(m: dict) -> int:
    return m["victorias"] + m["derrotas"] + m["reinicios"]


def minutos_por_victoria(datos: dict, medido: dict[frozenset, dict], minimo: int = MIN_PELEAS) -> tuple[float, str] | None:
    """Lo rapido que es un equipo: (minutos por victoria, de donde sale). Manda lo que midio el bot en esta
    PC (con al menos ``minimo`` peleas); si no, lo medido en las pruebas y publicado en equipos.yaml."""
    m = medido.get(frozenset(datos.get("personajes") or []))
    if m and _peleas(m) >= minimo and m["por_hora"] > 0:
        return 60 / m["por_hora"], "tuyo"
    if datos.get("minutos"):
        return float(datos["minutos"]), "pruebas"
    return None


def mas_rapido(id_destino: str) -> dict | None:
    """El equipo mas rapido medido para un destino: {"datos", "minutos", "fuente", "peleas"}, o None si no hay
    ninguno medido. Si el modo juega con un equipo fijo, solo cuentan los que el bot sabe jugar.
    Se recomienda desde la primera victoria medida (lo pidio el usuario, 2026-10-29: mejor el mejor que hay
    ahora, aunque sea el unico, que nada); "peleas" dice cuanto fiarse."""
    todos = cargar_equipos()
    clave = clave_de_equipos(id_destino, todos)
    fijo = getattr(MODOS.get(id_destino), "equipo", None) is not None
    medido = medidas(clave)
    mejor = None
    for datos in todos.get(clave, []):
        if fijo and not datos.get("bot"):
            continue
        rapidez = minutos_por_victoria(datos, medido, minimo=1)
        if rapidez and (mejor is None or rapidez[0] < mejor["minutos"]):
            m = medido.get(frozenset(datos.get("personajes") or []))
            mejor = {"datos": datos, "minutos": rapidez[0], "fuente": rapidez[1],
                     "peleas": _peleas(m) if m and rapidez[1] == "tuyo" else 0}
    if not fijo:
        # Tambien tus equipos medidos que no estan en la lista (en los modos de cualquier equipo el bot sabe con
        # cuales jugaste por sus cartas): el mas rapido se recomienda aunque nadie lo haya publicado.
        conocidos = {frozenset(d.get("personajes") or []) for d in todos.get(clave, [])}
        for ids, m in medidas(id_destino).items():
            if ids in conocidos or m["por_hora"] <= 0:
                continue
            minutos = 60 / m["por_hora"]
            if mejor is None or minutos < mejor["minutos"]:
                por_nombre = [i for i in ids if i.startswith("equipo:")]  # Fuerte Solgres: el nombre del juego
                datos = {"nombre": "Tu equipo", "personajes": sorted(ids)}
                if por_nombre:
                    juego_nombre = por_nombre[0].split(":", 1)[1]
                    # Si un equipo de la lista tiene ese nombre (o "nombre_juego"), se muestra ese, con sus caras
                    datos = next((d for d in todos.get(clave, []) if _mismo_nombre(d.get("nombre_juego", ""), juego_nombre)
                                  or _mismo_nombre(d.get("nombre", ""), juego_nombre)),
                                 {"nombre": juego_nombre, "personajes": []})
                mejor = {"datos": datos, "minutos": minutos, "fuente": "tuyo", "peleas": _peleas(m)}
    return mejor


def texto_minutos(minutos: float) -> str:
    return f"{minutos:.1f}".replace(".", ",").replace(",0", "") + " min por victoria"


def opciones_contenido(equipos: dict) -> list[tuple[str, str]]:
    """(clave, texto) para elegir donde va un equipo: las pestanas que ya hay y luego cada piso."""
    salida = [(clave, texto) for clave, texto, _, _ in contenidos_con_equipos(equipos)]
    ya = {clave for clave, _ in salida}
    for c in CATALOGO:
        for d in c.destinos:
            if d.id not in ya:
                salida.append((d.id, f"{c.nombre} · {d.nombre}" if d.nombre else c.nombre))
    return salida


def contenidos_con_equipos(equipos: dict) -> list[tuple[str, str, object, bool]]:
    """(clave, texto del boton, contenido, el bot lo juega) en el orden del catalogo. La clave es un
    destino ("perros_piso4") o un contenido entero ("perros": el resto de sus pisos)."""
    salida = []
    for c in CATALOGO:
        for clave in [c.id] + [d.id for d in c.destinos if d.id != c.id]:
            if clave not in equipos:
                continue
            destino = next((d for d in c.destinos if d.id == clave), None)
            propio = (equipos.get("_pisos") or {}).get(clave)  # "Floors 1–2" o "" (sin pisos)
            if propio is not None:
                texto = f"{c.nombre} · {propio}" if propio else c.nombre
            elif destino and destino.nombre:
                texto = f"{c.nombre} · {destino.nombre}"
            elif len(c.destinos) > 1:
                otros = [d.nombre for d in c.destinos if d.id not in equipos]
                texto = f"{c.nombre} · {otros[0]}–{otros[-1].split()[-1]}" if len(otros) > 1 else c.nombre
            else:
                texto = c.nombre
            salida.append((clave, texto, c, clave in MODOS))
    return salida


def _nombre(pid: str, biblioteca: dict, nombres: dict) -> str:
    return biblioteca[pid].nombre if pid in biblioteca else nombres.get(pid, pid)


def _retrato(pj: P.Personaje | None, nombre: str, tengo: bool, tam=(68, 68), extra: str = "",
             detalle: str = "", margen: int = 40) -> QWidget:
    caja = QWidget(objectName="caja_retrato")
    caja.setStyleSheet("QWidget#caja_retrato { background: transparent; }")  # sin el fondo oscuro detras de cada cara
    caja.setFixedWidth(tam[0] + margen)
    if detalle:
        caja.setToolTip(detalle)
    capa = QVBoxLayout(caja)
    capa.setContentsMargins(0, 0, 0, 0)
    capa.setSpacing(2)
    foto = QLabel(alignment=Qt.AlignCenter)
    foto.setFixedSize(*tam)
    foto.setObjectName("foto_pj")
    # Como en Inicio: cuadro con la cara del artwork pegada al rostro (sin artwork, la del icono sin nivel ni sello)
    ruta, rostro = pj.rostro() if pj else (None, None)
    pix = iconos.cuadrado(ruta, tam[0], tema.ACENTO if tengo else tema.BORDE, rostro=rostro, radio=10)
    if pix:
        foto.setPixmap(pix if tengo else _en_gris(pix))
        foto.setStyleSheet("background: transparent;")  # el cuadro ya trae sus esquinas y su borde
    else:
        foto.setPixmap(iconos.pixmap("mdi6.account-question", 34, tema.TENUE))
    foto.setProperty("tengo", tengo)
    capa.addWidget(foto, 0, Qt.AlignHCenter)
    texto = QLabel(nombre, alignment=Qt.AlignHCenter | Qt.AlignTop, wordWrap=True)
    texto.setFixedWidth(tam[0] + margen)
    texto.setMinimumHeight(texto.fontMetrics().lineSpacing() * 3 + 4)  # que no se monte sobre la cara
    texto.setStyleSheet(f"color: {tema.TEXTO if tengo else tema.TENUE}; font-size: 8.5pt;")
    capa.addWidget(texto, 0, Qt.AlignHCenter)
    if extra:
        mas = QLabel(extra, alignment=Qt.AlignCenter)
        mas.setStyleSheet(f"color: {tema.ACENTO}; font-size: 8pt; font-weight: 700;")
        capa.addWidget(mas, 0, Qt.AlignHCenter)
    capa.addStretch()
    # Alto fijo: con las notas abiertas el layout encogia la tarjeta y el nombre se montaba sobre la cara.
    linea = texto.fontMetrics().lineSpacing()
    caja.setFixedHeight(tam[1] + linea * 4 + 16)
    return caja


class TarjetaEquipo(QFrame):
    """Un equipo recomendado: cabecera siempre visible y detalle desplegable."""

    def __init__(self, datos: dict, biblioteca: dict, abierto: bool, nombres: dict | None = None,
                 medida: dict | None = None, al_editar=None, al_borrar=None, compacto: bool = False,
                 rapidez: tuple[float, str] | None = None):
        """``compacto``: para una columna estrecha (Farmear): caras mas pequenas y cabecera corta."""
        super().__init__(objectName="tarjeta_equipo")
        capa = QVBoxLayout(self)
        capa.setContentsMargins(14, 12, 14, 12)
        self.medida = medida
        self.rapidez = rapidez
        self.cifras: QLabel | None = None

        nombres_extra = nombres or {}
        ids = datos.get("personajes") or []
        faltan = [pid for pid in ids if not (biblioteca.get(pid) and biblioteca[pid].tengo)]
        alternativas = datos.get("alternativas") or {}
        # Un hueco con alternativa cuenta como cubierto si tienes alguna de ellas.
        faltan = [pid for pid in faltan if not any(biblioteca.get(a) and biblioteca[a].tengo for a in alternativas.get(pid, []))]
        self.completo = not faltan

        cab = QHBoxLayout()
        nivel_texto, nivel_color = NIVELES.get(datos.get("nivel", ""), ("", tema.TENUE))
        nivel = QLabel(nivel_texto)
        nivel.setStyleSheet(f"background: {nivel_color}; color: {tema.FONDO}; border-radius: 9px; padding: 2px 10px; font-weight: 700;")
        cab.addWidget(nivel, 0, Qt.AlignVCenter)
        titulo = QLabel(datos.get("nombre", ""), objectName="nombre_pj" if compacto else "titulo_tarjeta", wordWrap=compacto)
        cab.addWidget(titulo, 1 if compacto else 0)
        if datos.get("bot"):
            bot = QLabel("Bot" if compacto else "  El bot lo juega")
            bot.setToolTip("El bot sabe jugar este equipo")
            bot.setStyleSheet(f"color: {tema.ACENTO}; font-weight: 700;")
            cab.addWidget(bot)
        if datos.get("propio"):
            tuyo = QLabel("  Tuyo · publicándose")
            tuyo.setStyleSheet(f"color: {tema.TENUE}; font-style: italic;")
            tuyo.setToolTip("Lo creaste tú: Lumen lo sube solo a la base de todos y llega con la próxima actualización.")
            cab.addWidget(tuyo)
        cab.addStretch()
        estado = QLabel()
        if self.completo:
            estado.setText(f"<span style='color:{tema.OK}'><b>Lo tienes completo</b></span>")
        else:
            nombres = [_nombre(p, biblioteca, nombres_extra) for p in faltan]
            # Con varios nombres largos la tarjeta se ensanchaba: solo cuantos (las caras en gris ya dicen cuales)
            texto = f"Te falta: {nombres[0]}" if len(nombres) == 1 else f"Te faltan {len(nombres)}"
            estado.setText(f"<span style='color:{tema.AVISO}'>{texto}</span>")
            estado.setToolTip("Te falta:\n" + "\n".join(f"• {n}" for n in nombres))
        cab.addWidget(estado)
        for funcion, icono, ayuda in ((al_editar, "mdi6.pencil", "Editar este equipo"),
                                      (al_borrar, "mdi6.delete-outline", "Borrar este equipo")):
            if funcion:
                b = QPushButton(objectName="chico")
                b.setFlat(True)
                b.setIcon(iconos.icono(icono, tema.TEXTO))
                b.setToolTip(ayuda)
                b.clicked.connect(funcion)
                cab.addWidget(b)
        self.flecha = QPushButton(objectName="chico")
        self.flecha.setFlat(True)
        self.flecha.clicked.connect(self._alternar)
        cab.addWidget(self.flecha)
        capa.addLayout(cab)
        if medida and medida["victorias"] + medida["derrotas"] + medida["reinicios"]:
            peleas = medida["victorias"] + medida["derrotas"] + medida["reinicios"]
            texto = (f"Medido por el bot: <b>{medida['por_hora']:.1f} victorias por hora</b> · "
                     f"gana el {medida['tasa']:.0f} % · {peleas} pelea{'s' if peleas != 1 else ''}")
            if peleas < MIN_PELEAS:
                texto += f" (aún pocas: desde {MIN_PELEAS} cuenta para el orden)"
            cifras = self.cifras = QLabel(texto, wordWrap=True)
            cifras.setStyleSheet(f"color: {tema.ACENTO};")
            cifras.setToolTip("Victorias por hora = victorias entre el tiempo total farmeando (incluye "
                              "menús, cargas y pociones). Junta lo que gana y lo rápido que es. Cuenta las "
                              "peleas del bot y las que jugaste tú con «Aprender de mí».")
            capa.addWidget(cifras)
        elif rapidez and rapidez[1] == "pruebas":
            cifras = self.cifras = QLabel(f"Medido en las pruebas: <b>{texto_minutos(rapidez[0])}</b>", wordWrap=True)
            cifras.setStyleSheet(f"color: {tema.ACENTO};")
            capa.addWidget(cifras)

        fila = QHBoxLayout()
        fila.setSpacing(4 if compacto else 10)
        for pid in ids:
            pj = biblioteca.get(pid)
            tengo = bool(pj and pj.tengo) or any(biblioteca.get(a) and biblioteca[a].tengo for a in alternativas.get(pid, []))
            nombre = _nombre(pid, biblioteca, nombres_extra)
            if pj and pj.color in P.NOMBRE_COLOR and pj.color != "sin definir":
                nombre += f" · {P.NOMBRE_COLOR[pj.color]}"  # hay varias versiones de casi todos
            extra = detalle = ""
            if pid in alternativas:
                # Debajo solo cuantas; la lista entera al pasar el raton.
                otros = []
                for a in alternativas[pid]:
                    texto = _nombre(a, biblioteca, nombres_extra)
                    if a in biblioteca and biblioteca[a].color in P.NOMBRE_COLOR:
                        texto += f" · {P.NOMBRE_COLOR[biblioteca[a].color]}"
                    otros.append(texto + (" ✓" if biblioteca.get(a) and biblioteca[a].tengo else ""))
                extra = f"+{len(otros)} opción" + ("es" if len(otros) > 1 else "")
                detalle = "También vale:\n" + "\n".join(f"• {o}" for o in otros)
            if compacto:
                fila.addWidget(_retrato(pj, nombre, tengo, tam=(54, 54), extra=extra, detalle=detalle, margen=24))
            else:
                fila.addWidget(_retrato(pj, nombre, tengo, extra=extra, detalle=detalle))
        fila.addStretch()
        capa.addLayout(fila)

        self.detalle = QLabel(datos.get("notas", ""), wordWrap=True, objectName="tenue")
        self.detalle.setContentsMargins(4, 6, 4, 0)
        capa.addWidget(self.detalle)
        self.abierto = abierto
        self._mostrar()

    def marcar_rapido(self):
        """El mas rapido de los medidos: lo dice delante de su medida."""
        if self.cifras is not None:
            self.cifras.setText("⚡ <b>Más rápido</b> · " + self.cifras.text())

    def _alternar(self):
        self.abierto = not self.abierto
        self._mostrar()

    def _mostrar(self):
        self.detalle.setVisible(self.abierto)
        self.flecha.setIcon(iconos.icono("mdi6.chevron-up" if self.abierto else "mdi6.chevron-down", tema.TEXTO))
        self.flecha.setToolTip("Ocultar detalles" if self.abierto else "Ver como se juega")

    def mousePressEvent(self, evento):
        self._alternar()
        super().mousePressEvent(evento)

    def resizeEvent(self, evento):
        # Las notas ocupan varias lineas: su alto depende del ancho. Sin esto, si no caben todas las
        # tarjetas, Qt encoge la abierta y el texto se monta sobre las caras.
        super().resizeEvent(evento)
        alto = self.detalle.heightForWidth(self.detalle.width()) if self.detalle.isVisible() else 0
        if alto > 0 and self.detalle.minimumHeight() != alto:
            self.detalle.setMinimumHeight(alto)


def clave_de_equipos(id_destino: str, equipos: dict | None = None) -> str:
    """Donde estan los equipos de un destino: con su id ("perros_piso4") o, si no tiene, los de su
    contenido entero ("rata" = todos sus pisos)."""
    equipos = cargar_equipos() if equipos is None else equipos
    if id_destino in equipos:
        return id_destino
    contenido = contenido_de(id_destino)
    return contenido.id if contenido and contenido.id in equipos else id_destino


def tarjetas_equipos(clave: str, admin: bool = False, al_editar=None, al_borrar=None,
                     compacto: bool = False) -> list["TarjetaEquipo"]:
    """Las tarjetas de los equipos de un contenido, en orden: primero los medidos, del mas rapido al mas
    lento (ver minutos_por_victoria; el primero lleva "Mas rapido"), y luego el resto como estan en la lista. Viene
    abierto el mejor que ya puedes armar (o el primero si no tienes ninguno)."""
    biblioteca = P.cargar()
    todos = cargar_equipos()
    medido = medidas(clave)
    tarjetas = []
    for datos in todos.get(clave, []):
        propio = admin and datos.get("propio")
        tarjetas.append(TarjetaEquipo(
            datos, biblioteca, abierto=False, nombres=todos.get("_nombres") or {},
            medida=medido.get(frozenset(datos.get("personajes") or [])),
            al_editar=(lambda _=False, d=datos: al_editar(d)) if propio and al_editar else None,
            al_borrar=(lambda _=False, d=datos: al_borrar(d)) if propio and al_borrar else None,
            compacto=compacto, rapidez=minutos_por_victoria(datos, medido),
        ))

    medidos = sorted((t for t in tarjetas if t.rapidez), key=lambda t: t.rapidez[0])
    tarjetas = medidos + [t for t in tarjetas if not t.rapidez]
    if medidos:
        medidos[0].marcar_rapido()
    abierta = next((t for t in tarjetas if t.completo), tarjetas[0] if tarjetas else None)
    if abierta is not None:
        abierta.abierto = True
        abierta._mostrar()
    return tarjetas


class DialogoEquipo(QDialog):
    """Crear o editar un equipo del admin: donde va, nombre, nivel, los 4 heroes y notas."""

    def __init__(self, padre, opciones: list[tuple[str, str]], biblioteca: dict, clave: str = "", datos: dict | None = None):
        super().__init__(padre)
        datos = datos or {}
        self.setWindowTitle("Editar equipo" if datos else "Agregar equipo")
        self.setMinimumWidth(560)
        capa = QVBoxLayout(self)
        form = QFormLayout()
        self.contenido = QComboBox()
        for c, texto in opciones:
            self.contenido.addItem(texto, c)
        self.contenido.setCurrentIndex(max(0, self.contenido.findData(clave)))
        self.nombre = QLineEdit(datos.get("nombre", ""), placeholderText="p. ej. Escanor y Freyr")
        self.nivel = QComboBox()
        for n, (texto, _) in NIVELES.items():
            self.nivel.addItem(texto, n)
        self.nivel.setCurrentIndex(max(0, self.nivel.findData(datos.get("nivel", "alternativa"))))
        form.addRow("Contenido", self.contenido)
        form.addRow("Nombre", self.nombre)
        form.addRow("Nivel", self.nivel)
        # Los 4 heroes: se escribe parte del nombre y se elige (los tuyos primero).
        heroes = sorted(biblioteca.values(), key=lambda p: (not p.tengo, p.nombre.lower(), p.color))
        self.puestos = []
        actuales = datos.get("personajes") or []
        for i in range(4):
            combo = QComboBox(editable=True)
            combo.setInsertPolicy(QComboBox.NoInsert)
            combo.addItem("", "")
            for p in heroes:
                combo.addItem(f"{p.nombre} · {P.NOMBRE_COLOR.get(p.color, '?')}" + ("  ✓" if p.tengo else ""), p.id)
            completar = QCompleter(combo.model(), combo)
            completar.setFilterMode(Qt.MatchContains)
            completar.setCaseSensitivity(Qt.CaseInsensitive)
            combo.setCompleter(completar)
            if i < len(actuales):
                combo.setCurrentIndex(max(0, combo.findData(actuales[i])))
            form.addRow(f"Puesto {i + 1}", combo)
            self.puestos.append(combo)
        self.notas = QTextEdit(datos.get("notas", ""))
        self.notas.setPlaceholderText("Cómo se juega, equipo, enlaces...")
        self.notas.setFixedHeight(90)
        form.addRow("Notas", self.notas)
        capa.addLayout(form)
        botones = QHBoxLayout()
        botones.addStretch()
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        guardar = QPushButton("Guardar", objectName="primario")
        guardar.clicked.connect(self._guardar)
        botones.addWidget(cancelar)
        botones.addWidget(guardar)
        capa.addLayout(botones)
        self.resultado: tuple[str, dict] | None = None

    def _guardar(self):
        ids = []
        for combo in self.puestos:
            # Si se escribio el nombre exacto sin elegirlo de la lista, buscarlo igual.
            i = combo.findText(combo.currentText())
            ids.append(combo.itemData(i) if i >= 0 else "")
        if not self.nombre.text().strip():
            QMessageBox.warning(self, "Equipo", "Ponle un nombre al equipo.")
            return
        if not all(ids) or len(set(ids)) != 4:
            QMessageBox.warning(self, "Equipo", "Elige 4 héroes distintos (escribe parte del nombre y elígelo de la lista).")
            return
        datos = {"nombre": self.nombre.text().strip(), "nivel": self.nivel.currentData(), "personajes": ids}
        if self.notas.toPlainText().strip():
            datos["notas"] = self.notas.toPlainText().strip()
        self.resultado = (self.contenido.currentData(), datos)
        self.accept()


class PaginaEquipos(Pagina):
    titulo = "Equipos"
    subtitulo = "Del mejor al más difícil."

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.b_agregar = QPushButton(" Agregar equipo", objectName="primario")
        self.b_agregar.setIcon(iconos.icono("mdi6.plus", tema.SOBRE_ACENTO))
        self.b_agregar.setToolTip("Modo administrador: crea un equipo. El bot lo medirá cuando juegue con él.")
        self.b_agregar.clicked.connect(lambda: self._editar())
        self.acciones.addWidget(self.b_agregar)
        self.b_aprender = QPushButton(" Aprender de mí", objectName="chico")
        self.b_aprender.setIcon(iconos.icono("mdi6.school-outline", tema.TEXTO))
        self.b_aprender.setToolTip("Modo administrador: juegas tú a mano y el bot mira y apunta tus jugadas.")
        self.b_aprender.clicked.connect(self._aprender)
        self.acciones.addWidget(self.b_aprender)
        self.selector = QGridLayout()  # en filas de 3: los nombres de las bestias son largos
        self.selector.setHorizontalSpacing(8)
        self.selector.setVerticalSpacing(6)
        self.grupo = QButtonGroup(self, exclusive=True)
        self.grupo.buttonClicked.connect(lambda _: self.al_mostrar())
        self.contenidos = {}
        self._construir_selector(config.obtener("ultimo_modo"))
        self.cuerpo.addLayout(self.selector)
        self.subtitulo_modo = QLabel(objectName="tenue")
        self.cuerpo.addWidget(self.subtitulo_modo)

        self.zona = QWidget()
        self.lista = QVBoxLayout(self.zona)
        self.lista.setSpacing(10)
        desplazar = QScrollArea(widgetResizable=True)
        desplazar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        desplazar.setWidget(self.zona)
        self.cuerpo.addWidget(desplazar, 1)
        self.al_mostrar()

    def _construir_selector(self, elegida: str):
        """Un boton por contenido con equipos (se rehace si el admin crea uno en un contenido nuevo)."""
        for b in self.grupo.buttons():
            self.grupo.removeButton(b)
            b.setParent(None)
        self.contenidos = {}
        for i, (clave, texto, contenido, juega) in enumerate(contenidos_con_equipos(cargar_equipos())):
            b = QPushButton("  " + texto.replace("&", "&&"), objectName="chip", checkable=True)
            foto = contenido.foto
            pix = iconos.redondo(foto, 28) if foto and foto.is_file() else None
            if pix:
                from PyQt5.QtGui import QIcon

                b.setIcon(QIcon(pix))
            else:
                b.setIcon(iconos.icono(contenido.icono, tema.TEXTO))
            b.setProperty("modo", clave)
            b.setToolTip(texto)
            b.setChecked(clave == elegida or i == 0)
            self.contenidos[clave] = (contenido, juega)
            self.grupo.addButton(b)
            self.selector.addWidget(b, i // 3, i % 3)

    def _clave_actual(self) -> str:
        boton = self.grupo.checkedButton()
        return boton.property("modo") if boton else ""

    def _editar(self, datos: dict | None = None):
        clave_vieja = self._clave_actual()
        dialogo = DialogoEquipo(self, opciones_contenido(cargar_equipos()), P.cargar(), clave_vieja, datos)
        if dialogo.exec_() != QDialog.Accepted or not dialogo.resultado:
            return
        clave, nuevo = dialogo.resultado
        guardar_propio(clave, nuevo, (clave_vieja, datos["_indice"]) if datos else None)
        self._construir_selector(clave)
        self.al_mostrar()
        self.app.publicar()

    def _aprender(self):
        from PyQt5.QtWidgets import QInputDialog

        from lumen.modos.aprender import Aprender

        opciones = opciones_contenido(cargar_equipos())
        textos = [texto for _, texto in opciones]
        actual = next((i for i, (c, _) in enumerate(opciones) if c == self._clave_actual()), 0)
        texto, ok = QInputDialog.getItem(self, "Aprender de mí", "¿Qué vas a jugar?", textos, actual, False)
        if not ok:
            return
        clave = opciones[textos.index(texto)][0]
        aviso = (f"APRENDER DE MÍ · {texto}\n\n"
                 "Juega tú las peleas a mano, como siempre. El bot no hace ningún clic: solo mira.\n\n"
                 "• Reconoce tu equipo por las cartas de la mano.\n"
                 "• En cada turno apunta tu mano, la fase y qué cartas juegas (clic) o mueves (arrastre).\n"
                 "• Al acabar cada pelea la guarda en capturas\\aprendizaje y la cuenta para medir el equipo aquí.\n\n"
                 "Deja la ventana del juego a la vista. F10 o Detener para terminar.")
        if QMessageBox.question(self, "Aprender de mí", aviso) == QMessageBox.Yes:
            self.app.farmear.ejecutar_herramienta(Aprender({"contenido": clave, "nombre_contenido": texto}))

    def _borrar(self, datos: dict):
        if QMessageBox.question(self, "Borrar equipo", f"¿Borrar el equipo «{datos.get('nombre', '')}»?") == QMessageBox.Yes:
            clave = self._clave_actual()
            borrar_propio(clave, datos["_indice"])
            self._construir_selector(clave)
            self.al_mostrar()

    def al_mostrar(self):
        while self.lista.count():
            w = self.lista.takeAt(0).widget()
            if w:
                w.setParent(None)
        admin = bool(config.obtener("modo_admin"))
        self.b_agregar.setVisible(admin)
        self.b_aprender.setVisible(admin)
        clave = self._clave_actual()
        contenido, juega = self.contenidos.get(clave, (None, False))
        if contenido:
            estado = "El bot ya lo farmea" if juega else "El bot todavía no lo farmea"
            self.subtitulo_modo.setText(f"{contenido.descripcion} · {estado}. Haz clic en un equipo para ver cómo se juega.")
        tarjetas = tarjetas_equipos(clave, admin, self._editar, self._borrar)
        for t in tarjetas:
            self.lista.addWidget(t)
        if not tarjetas:
            self.lista.addWidget(QLabel("Todavía no hay equipos recomendados para este contenido.", objectName="tenue"))
        # Relleno al final en vez de alinear arriba: con AlignTop Qt calculaba mal el alto de las notas
        # (texto en varias lineas) y montaba el texto sobre las caras.
        self.lista.addStretch(1)

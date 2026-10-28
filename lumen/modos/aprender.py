"""Modo "Aprender de mi" (administrador): el jugador pelea a mano y el bot solo mira.

No hace ningun clic. En cada pelea:
- reconoce el equipo por las cartas de la mano (comparandolas con las de todos los heroes de la base);
- en cada turno guarda la mano con que empieza, la fase y lo que hace el jugador: un clic en una carta
  es "jugar" y un arrastre es "mover" (para fusionar o reordenar). Los clics se leen del raton con
  pynput, en las coordenadas de la ventana del juego;
- al terminar guarda la pelea en capturas/aprendizaje/<fecha>.yaml (con una foto por turno) y la cuenta
  en el historial para medir el equipo en la pagina Equipos (victorias por hora).

Es la base para que el bot aprenda a jugar cualquier equipo copiando lo que hace el jugador.
"""

import threading
import time
from collections import Counter

import cv2
import numpy as np
import yaml

from lumen import botin, cartas, historial, juego, recompensas
from lumen import personajes as P
from lumen.control import control
from lumen.equipo import Equipo, Puesto
from lumen.motor import Modo, TerminarModo
from lumen.rutas import RAIZ
from lumen.vision import Plantilla, guardar_imagen, recortar

CARPETA = RAIZ / "capturas" / "aprendizaje"
ARRASTRE_PX = 25  # mas que esto entre pulsar y soltar = arrastrar (mover/fusionar), no jugar
VOTOS_EQUIPO = 2  # veces que tiene que salir un heroe en la mano para darlo por parte del equipo
SIN_PELEA_S = 20  # sin boton de pausa ni pantalla de resultado durante este tiempo = pelea abandonada
# Medido en 2 peleas reales y menus: el boton de pausa da 0.99-1.00 en pelea y <=0.63 fuera; los
# carteles de fase 0.96-1.00 en su fase pero hasta 0.82 por error en un menu; la victoria >=0.89.
UMBRAL_PAUSA = 0.9
# Demonios (Indura...): no hay boton de pausa; en pelea se ve AUTO (0.92-0.98, fuera <=0.48), la mano tiene
# 7 cartas y el turno se juega en una fila de 6 casillas. Medido en una pelea real de Indura (Chaos).
DEMONIOS = {"demonio_rojo", "demonio_gris", "howlex", "bellmoth", "demonio_original", "indura"}
AUTO_DEMONIO = Plantilla("demons/auto.jpg")
DESTRUIDO = Plantilla("demons/demons_destroyed.png")
UMBRAL_FASE = 0.9
UMBRAL_RESULTADO = 0.85
PARECIDO_HUELLA = 4.0  # diferencia media (0-255) para dar una carta por ya vista: brillo/ruido ~1-2, otra carta 20+


class Raton:
    """Clics del jugador (pynput) en coordenadas de pantalla, con su hora."""

    def __init__(self):
        self.eventos: list[dict] = []
        self._lock = threading.Lock()
        self._pulsado = None
        self._oyente = None

    def iniciar(self):
        from pynput import mouse

        def al_clic(x, y, boton, pulsado):
            if boton != mouse.Button.left:
                return
            if pulsado:
                self._pulsado = (x, y, time.time())
                return
            if self._pulsado is None:
                return
            x0, y0, t0 = self._pulsado
            self._pulsado = None
            with self._lock:
                self.eventos.append({"t": t0, "desde": (x0, y0), "hasta": (x, y)})

        self._oyente = mouse.Listener(on_click=al_clic)
        self._oyente.daemon = True
        self._oyente.start()

    def parar(self):
        if self._oyente:
            self._oyente.stop()

    def sacar(self) -> list[dict]:
        with self._lock:
            eventos, self.eventos = self.eventos, []
        return eventos


class IndiceCartas:
    """Las cartas de todos los heroes de la base, para reconocer el equipo por la mano.

    Son mas de 1000 plantillas: compararlas todas a tamano real tarda ~0.35 s por carta (unos 3 s por
    mano). Por eso primero se compara a mitad de tamano (mucho mas rapido), se quedan las CANDIDATAS
    mas parecidas y solo esas se comparan a tamano real. Con 150 cartas simuladas da el mismo
    resultado que compararlas todas, ~4 veces mas rapido. Y una carta que sigue en la mano no se
    vuelve a mirar (memoria por su dibujo).
    """

    CANDIDATAS = 30

    def __init__(self):
        self.plantillas = []  # (pid, carta, Plantilla, umbral)
        for pj in P.cargar().values():
            for c in pj.cartas.values():
                if c.boton:
                    continue
                plantilla, umbral = pj.plantilla(c.id)
                if plantilla is not None and plantilla.disponible:
                    self.plantillas.append((pj.id, c.id, plantilla, umbral))
        self.mitades = [_mitad(p.imagenes[0]) for _, _, p, _ in self.plantillas]
        self._memoria: list[tuple[np.ndarray, str | None]] = []  # (huella, "heroe.carta") de cartas ya vistas

    def heroe_de(self, carta: cartas.Carta) -> str | None:
        nombre = self.carta_de(carta)
        return nombre.split(".")[0] if nombre else None

    def carta_de(self, carta: cartas.Carta) -> str | None:
        """Que carta es: "heroe.carta" (p. ej. "cleaner_enjin_claro.skill_2"), o None si no se parece a ninguna."""
        if carta.imagen is None or carta.tipo in (cartas.TipoCarta.SUELO, cartas.TipoCarta.NINGUNA):
            return None
        huella = _huella(carta.imagen)
        for vista, nombre in self._memoria:
            if float(np.abs(vista - huella).mean()) < PARECIDO_HUELLA:
                return nombre
        pequena = _mitad(carta.imagen)
        parecidos = []
        for i, ref in enumerate(self.mitades):
            if ref.shape[0] <= pequena.shape[0] and ref.shape[1] <= pequena.shape[1]:
                parecidos.append((float(cv2.matchTemplate(pequena, ref, cv2.TM_CCOEFF_NORMED).max()), i))
        mejor, valor_mejor = None, 0.0
        for _, i in sorted(parecidos, reverse=True)[: self.CANDIDATAS]:
            pid, cid, plantilla, umbral = self.plantillas[i]
            valor, _ = plantilla.confianza(carta.imagen)
            if valor >= umbral and valor > valor_mejor:
                mejor, valor_mejor = f"{pid}.{cid}", valor
        self._memoria = self._memoria[-300:] + [(huella, mejor)]
        return mejor


def _mitad(imagen):
    return cv2.resize(imagen, (imagen.shape[1] // 2, imagen.shape[0] // 2), interpolation=cv2.INTER_AREA)


def _huella(imagen) -> np.ndarray:
    """Resumen del dibujo de una carta (gris, 8x16): casi igual mientras la carta no cambia."""
    return cv2.cvtColor(cv2.resize(imagen, (8, 16), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32)


class Aprender(Modo):
    id = "aprender"
    nombre = "Aprender de mí"
    titulo_juego = "Aprender de mí"
    descripcion = "Juegas tú a mano; el bot mira y apunta tu equipo, tus jugadas y el resultado."
    guardar_historial = False  # cada equipo se guarda aparte en el historial (ver _cerrar_sesion)
    pausa_entre_pasos = 0.25
    nombres_estados = {
        "esperar_pelea": "Esperando a que empiece una pelea",
        "pelea": "Mirando cómo juegas",
        "resultado": "Guardando la pelea",
    }

    def __init__(self, valores: dict):
        super().__init__(valores)
        self.contenido = valores.get("contenido", "")
        self.demonio = self.contenido in DEMONIOS
        self.nombre_contenido = valores.get("nombre_contenido", self.contenido)
        self.raton = Raton()
        self.indice: IndiceCartas | None = None
        self.peleas = 0
        self.ultimo_resultado, self.foto_hecha, self.previa, self.ok_visto_desde = "", True, None, None
        self.sesion = self._sesion_nueva(())
        self._pelea_nueva()

    # ------------------------------------------------------------------ estados
    def estado_inicial(self):
        return "esperar_pelea"

    def estados(self):
        return {"esperar_pelea": self.esperar_pelea, "pelea": self.pelea, "resultado": self.resultado}

    def en_zona_segura(self) -> bool:
        return self.estado == "esperar_pelea"

    def ejecutar(self):
        self.log("Cargando las cartas de todos los héroes para reconocer tu equipo...")
        self.indice = IndiceCartas()
        self.raton.iniciar()
        self.log(f"Listo ({len(self.indice.plantillas)} cartas). Juega tú: yo solo miro y apunto.", "ok")
        try:
            super().ejecutar()
        finally:
            self.raton.parar()

    def esperar_pelea(self, p, o):
        self.raton.sacar()  # los clics fuera de una pelea (menus) no interesan
        if self._en_pelea(p):
            self._pelea_nueva()
            self.log("Empieza una pelea: te miro.", "ok")
            control.actividad()
            return "pelea"
        return None

    def pelea(self, p, o):
        if (juego.victoria.esta(p, UMBRAL_RESULTADO) or juego.criatura_destruida.esta(p, UMBRAL_RESULTADO)
                or (self.demonio and DESTRUIDO.esta(p, 0.6))):
            return self._terminar_pelea("victoria", p)
        if juego.derrota.esta(p, UMBRAL_RESULTADO):
            return self._terminar_pelea("derrota", p)
        if not self._en_pelea(p):
            # Transiciones entre fases o turnos quitan la pausa un momento; si dura, se abandono.
            if time.time() - self.ultima_vez_en_pelea > SIN_PELEA_S:
                self.log("Ya no veo la pelea (¿te rendiste o saliste?): la guardo como abandonada.", "aviso")
                return self._terminar_pelea("abandonada", p)
            self._procesar_clics()
            return None
        self.ultima_vez_en_pelea = time.time()
        self._ver_fase(p)
        huecos = cartas.casillas_libres_demonio(p) if self.demonio else cartas.contar_huecos(p)
        mano = self._leer_mano(p)
        if self._mano_a_la_vista(p, mano) and huecos > 0:
            self._reconocer_equipo(mano)
            nombres = [c.nombre for c in mano]
            if huecos == (6 if self.demonio else 4) and not self.turno_abierto:
                self._abrir_turno(p, mano)
            if self.turno_abierto:
                self.manos.append((time.time(), mano, o))
                self.manos = self.manos[-20:]
            if nombres != self.ultimos_nombres:
                control.actividad()
                self.ultimos_nombres = nombres
        elif huecos == 0 and self.turno_abierto:
            self._cerrar_turno()
        self._procesar_clics()
        return None

    def resultado(self, p, o):
        # Tras ganar, foto de las recompensas cuando la pantalla con OK este quieta (como el bot).
        if self.ultimo_resultado == "victoria" and not self.foto_hecha and juego.ok.esta(p):
            self.ok_visto_desde = self.ok_visto_desde or time.time()
            if botin.quieta(self.previa, p) or time.time() - self.ok_visto_desde > 6:
                try:
                    recompensas.guardar(p, modo=self.contenido, nombre_modo=f"{self.nombre_contenido} (a mano)",
                                        sesion=self.sesion["inicio"], victoria=self.sesion["victorias"])
                    self.log("Foto de recompensas guardada.", "debug")
                except Exception as error:
                    self.log(f"No pude guardar la foto de recompensas: {error}", "aviso")
                self.foto_hecha = True
            self.previa = p
            return None
        # Esperar a que salga de la pantalla de resultado antes de buscar la siguiente pelea.
        if not (juego.victoria.esta(p, UMBRAL_RESULTADO) or juego.derrota.esta(p, UMBRAL_RESULTADO) or self._en_pelea(p)):
            return "esperar_pelea"
        return None

    # ----------------------------------------------------------------- la pelea
    def _pelea_nueva(self):
        self.pelea_actual = {"inicio": time.time(), "turnos": []}
        self.turno: dict | None = None
        self.turno_abierto = False
        self.manos: list = []  # (hora, mano, origen) de este turno, para saber que carta habia bajo cada clic
        self.ultimos_nombres: list = []
        self.fase = 0
        self.votos: Counter = Counter()
        self.equipo_ids: tuple = ()
        self.equipo: Equipo | None = None
        self.ultima_vez_en_pelea = time.time()

    def _en_pelea(self, p) -> bool:
        if self.demonio:
            return AUTO_DEMONIO.esta(p, UMBRAL_PAUSA)
        return juego.pausa.esta(p, UMBRAL_PAUSA)

    def _leer_mano(self, p):
        return cartas.leer_mano_demonio(p) if self.demonio else cartas.leer_mano(p)

    def _mano_a_la_vista(self, p, mano=None) -> bool:
        mano = mano if mano is not None else self._leer_mano(p)
        return sum(1 for c in mano if c.tipo in (cartas.TipoCarta.NORMAL, cartas.TipoCarta.ULTI)) >= 3

    def _ver_fase(self, p):
        for n, plantilla in ((1, juego.fase_1), (2, juego.fase_2), (3, juego.fase_3_perros)):
            if n > self.fase and plantilla.esta(p, UMBRAL_FASE):
                self.fase = n
                self.log(f"Fase {n}.", "debug")

    def _reconocer_equipo(self, mano):
        if self.equipo is not None:
            self.equipo.etiquetar(mano)
            return
        for carta in mano:
            pid = self.indice.heroe_de(carta)
            if pid:
                self.votos[pid] += 1
        # Solo cuentan los heroes vistos varias veces: una carta suelta mal reconocida no entra al equipo.
        # En Indura solo salen cartas de 3 heroes (el 4.o no reparte), asi que con 3 seguros tambien vale.
        seguros = [pid for pid, n in self.votos.most_common() if n >= VOTOS_EQUIPO]
        turnos = len(self.pelea_actual["turnos"])
        if len(seguros) >= 4 or (len(seguros) >= 3 and (self.demonio or turnos >= 3)):
            ids = tuple(seguros[:4])
            self.equipo_ids = ids
            puestos = [Puesto("", (), pid) for pid in ids]
            self.equipo = Equipo("aprendido", "Equipo del jugador", puestos, obligatorias=set())
            nombres = ", ".join(self.equipo.biblioteca[pid].nombre for pid in ids if pid in self.equipo.biblioteca)
            self.log(f"Tu equipo: {nombres}.", "ok")
            self.equipo.etiquetar(mano)

    def _abrir_turno(self, p, mano):
        self.turno_abierto = True
        n = len(self.pelea_actual["turnos"]) + 1
        self.turno = {"turno": n, "fase": self.fase, "inicio": round(time.time() - self.pelea_actual["inicio"], 1),
                      "mano": [str(c) for c in mano], "_mano": mano, "acciones": []}
        self.pelea_actual["turnos"].append(self.turno)
        self.pelea_actual.setdefault("_fotos", []).append(p.copy())
        self.log(f"Turno {n} (fase {self.fase or '?'}): " + " ".join(str(c) for c in mano), "debug")

    def _cerrar_turno(self):
        self._procesar_clics()
        self.turno_abierto = False
        if self.turno is not None:
            jugadas = [a["carta"] for a in self.turno["acciones"] if a["accion"] == "jugar"]
            self.log(f"Jugaste: {', '.join(jugadas) if jugadas else 'nada'}.", "debug")

    def _carta_en(self, punto_pantalla, hora):
        """La carta que habia en la mano bajo ese punto justo antes del clic."""
        anteriores = [m for m in self.manos if m[0] <= hora] or self.manos[:1]
        if not anteriores:
            return None
        _, mano, origen = anteriores[-1]
        x, y = punto_pantalla[0] - origen[0], punto_pantalla[1] - origen[1]
        for carta in mano:
            cx, cy, cw, ch = carta.rect
            if cx <= x < cx + cw and cy <= y < cy + ch:
                return carta
        return None

    def _procesar_clics(self):
        for e in self.raton.sacar():
            if self.turno is None or not self.manos:
                continue
            carta = self._carta_en(e["desde"], e["t"])
            if carta is None or carta.tipo in (cartas.TipoCarta.SUELO, cartas.TipoCarta.NINGUNA):
                continue  # clic fuera de la mano o en un hueco vacio (objetivo, talento...): no se apunta
            dx, dy = e["hasta"][0] - e["desde"][0], e["hasta"][1] - e["desde"][1]
            accion = {"t": round(e["t"] - self.pelea_actual["inicio"], 1), "carta": carta.nombre or "?",
                      "posicion": carta.posicion + 1, "rango": carta.rango.name.lower()}
            if (dx * dx + dy * dy) ** 0.5 > ARRASTRE_PX:
                destino = self._carta_en(e["hasta"], e["t"])
                accion.update(accion="mover", a_posicion=destino.posicion + 1 if destino else None)
            else:
                accion["accion"] = "jugar"
            self.turno["acciones"].append(accion)
            self.log(f"   {accion['accion']} {accion['carta']} (posición {accion['posicion']})", "debug")

    def _terminar_pelea(self, resultado: str, p):
        if self.turno_abierto:
            self._cerrar_turno()
        fin = time.time()
        pelea = self.pelea_actual
        fotos = pelea.pop("_fotos", [])
        for turno in pelea["turnos"]:  # las manos de antes de reconocer el equipo, ya con nombre
            mano = turno.pop("_mano", None)
            if mano is not None and self.equipo is not None:
                self.equipo.etiquetar(mano)
                turno["mano"] = [str(c) for c in mano]
        pelea.update(contenido=self.contenido, resultado=resultado, fin=fin,
                     duracion=round(fin - pelea["inicio"], 1), equipo=list(self.equipo_ids))
        nombre = time.strftime("%Y%m%d_%H%M%S", time.localtime(pelea["inicio"]))
        try:
            CARPETA.mkdir(parents=True, exist_ok=True)
            (CARPETA / f"{nombre}.yaml").write_text(
                yaml.safe_dump(pelea, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")
            for i, foto in enumerate(fotos, start=1):  # la mano y la barra de cada turno, para revisarlas
                guardar_imagen(CARPETA / nombre / f"turno_{i:02d}.jpg", recortar(foto, (0, 560, foto.shape[1], foto.shape[0])))
        except Exception as error:
            self.log(f"No pude guardar la pelea: {error}", "aviso")
        self.peleas += 1
        minutos = pelea["duracion"] / 60
        self.log(f"Pelea {self.peleas}: {resultado} en {minutos:.1f} min y {len(pelea['turnos'])} turnos. Guardada.",
                 "ok" if resultado == "victoria" else "aviso")
        self._contar(resultado)
        self.ultimo_resultado, self.foto_hecha, self.previa, self.ok_visto_desde = resultado, False, None, None
        return "resultado"

    # ------------------------------------------- medicion del equipo (historial)
    def _sesion_nueva(self, equipo: tuple) -> dict:
        return {"inicio": time.time(), "equipo": list(equipo), "victorias": 0, "derrotas": 0, "reinicios": 0}

    def _contar(self, resultado: str):
        if tuple(self.sesion["equipo"]) != self.equipo_ids:
            # Cambiaste de equipo: lo de antes se cuenta para el equipo anterior.
            self._cerrar_sesion()
            self.sesion = self._sesion_nueva(self.equipo_ids)
            self.sesion["inicio"] = self.pelea_actual["inicio"]
        clave = {"victoria": "victorias", "derrota": "derrotas"}.get(resultado, "reinicios")
        self.sesion[clave] += 1
        self.sesion["fin"] = time.time()  # el tiempo de este equipo acaba con su ultima pelea
        self.publicar_stats(victorias=self.sesion["victorias"], derrotas=self.sesion["derrotas"], peleas=self.peleas)

    def _cerrar_sesion(self):
        s = self.sesion
        if not s["equipo"] or not (s["victorias"] + s["derrotas"] + s["reinicios"]):
            return
        historial.registrar({"fin": time.time(), **s, "modo": self.contenido, "nombre": self.nombre_contenido,
                             "manual": True})

    def al_terminar(self):
        self._cerrar_sesion()
        self.log(f"Aprendizaje terminado: {self.peleas} pelea(s) guardada(s) en capturas\\aprendizaje.", "ok")

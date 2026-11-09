"""Indura (F10 y pausa en la espera), botin (uniones), imagenes en espanol, premios y Aprender de mi."""

import random
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import entorno  # noqa: F401  (antes que lumen)

import cv2
import numpy as np

from lumen import botin, entrada, estrategias, premios, recompensas, vision
from lumen.cartas import Carta, Rango, TipoCarta as T
from lumen.control import Detenido, control
from lumen.rutas import IMAGENES
import lumen.modos.indura as M


class Indura(unittest.TestCase):
    def setUp(self):
        control.reiniciar()
        self.addCleanup(control.reiniciar)
        for objeto, nombre, valor in ((entrada, "apuntar", lambda *a: None), (entrada, "pulsar", lambda *a: None)):
            p = mock.patch.object(objeto, nombre, valor)
            p.start()
            self.addCleanup(p.stop)
        aceptar = mock.MagicMock()
        aceptar.buscar.return_value = (1, 1, 5, 5)
        p = mock.patch.object(M, "ACEPTAR", aceptar)
        p.start()
        self.addCleanup(p.stop)

    def test_f10_durante_la_espera(self):
        threading.Timer(0.3, control.detener).start()
        inicio = time.time()
        with self.assertRaises(Detenido):
            M.Indura({"espera": "9.3"}).buscar(None, (0, 0))
        self.assertLess(time.time() - inicio, 1.5)

    def test_pausa_deja_pasar_la_invitacion(self):
        threading.Timer(0.3, control.pausar).start()
        inicio = time.time()
        self.assertIsNone(M.Indura({"espera": "9.3"}).buscar(None, (0, 0)))
        self.assertLess(time.time() - inicio, 1.5)

    def test_pc_normal_no_adelanta(self):
        """PC rapido: capturas cada ~0,2 s y 0,1 s para buscar Accept. Se toca igual que siempre."""
        self.assertEqual(M.adelanto_por_lentitud(100.0, 100.2, 100.3), 0.0)

    def test_pc_lento_adelanta_el_toque(self):
        """Maquina virtual: capturas cada 1,2 s y 0,7 s para buscar. Se ve tarde y el ultimo vistazo tambien
        tarda: se descuenta lo que pasa de lo normal (0,7 + 0,6 - 0,3) + (0,7 - 0,15) = 1,55 s."""
        self.assertAlmostEqual(M.adelanto_por_lentitud(100.0, 101.2, 101.9), 1.55)

    def test_adelanto_con_limite_y_sin_datos(self):
        self.assertEqual(M.adelanto_por_lentitud(100.0, 110.0, 115.0), M.ADELANTO_MAX)
        self.assertEqual(M.adelanto_por_lentitud(0.0, 0.0, 5.0), 0.0, "sin capturas medidas no se adelanta")

    def test_el_toque_llega_antes_en_un_pc_lento(self):
        """La espera de 9,3 s se acorta en lo que se adelanta (aqui se espera 0,6 s y se adelantan 0,5)."""
        ind = M.Indura({"espera": "0.6"})
        tocado = []
        for objeto, nombre, valor in ((entrada, "clic_rapido", lambda rect, o: tocado.append(time.perf_counter())),
                                      (ind, "capturar", lambda: (None, (0, 0))),
                                      (M, "adelanto_por_lentitud", lambda a, b, c: 0.5),
                                      (control, "esperar", lambda s: None)):
            q = mock.patch.object(objeto, nombre, valor)
            q.start()
            self.addCleanup(q.stop)
        inicio = time.perf_counter()
        ind.buscar(None, (0, 0))
        self.assertEqual(len(tocado), 1)
        self.assertLess(tocado[0] - inicio, 0.4, "toca a los ~0,1 s y no a los 0,6")

    def _buscando(self, ind, vistas):
        """Pantalla de busqueda sin invitacion; en la vigilancia, ACEPTAR responde segun 'vistas'."""
        capturas = []
        tocado = []
        no, si = mock.MagicMock(), mock.MagicMock()
        no.esta.return_value, si.esta.return_value = False, True
        M.ACEPTAR.buscar.side_effect = vistas
        M.ACEPTAR.esta.return_value = False  # tras el toque ya no esta
        for objeto, nombre, valor in ((entrada, "clic_rapido", lambda rect, o: tocado.append(rect)),
                                      (ind, "capturar", lambda: capturas.append(1) or (None, (0, 0))),
                                      (M, "CARGANDO", no), (M, "PREPARACION", no), (M, "CANCELAR_BUSQUEDA", si),
                                      (M, "TIEMPO_REAL", no), (control, "esperar", lambda s: None)):
            q = mock.patch.object(objeto, nombre, valor)
            q.start()
            self.addCleanup(q.stop)
        return capturas, tocado

    def test_mientras_espera_mira_solo_accept_muy_seguido(self):
        """En la maquina virtual cada vuelta tardaba mas de 2 s: ahora, sin invitacion, se vigila solo Accept."""
        ind = M.Indura({"espera": "0", "minutos_sin_invitacion": "0"})
        rect = (1, 1, 5, 5)
        capturas, tocado = self._buscando(ind, [None, None, rect, rect])
        self.assertEqual(ind.buscar("pantalla", (0, 0)), "preparar")
        self.assertEqual(tocado, [rect])
        self.assertEqual(len(capturas), 4, "2 vistazos rapidos hasta verla, el de antes del toque y el de despues")

    def test_vigilancia_sin_invitacion_vuelve_al_bucle(self):
        ind = M.Indura({"espera": "9.3", "minutos_sin_invitacion": "0"})
        capturas, tocado = self._buscando(ind, lambda *a: None)
        with mock.patch.object(M, "VIGILANCIA", 0.2):
            inicio = time.perf_counter()
            self.assertIsNone(ind.buscar("pantalla", (0, 0)))
        self.assertLess(time.perf_counter() - inicio, 1.0)
        self.assertGreater(len(capturas), 1)
        self.assertEqual(tocado, [])

    def _con_diario(self, valores):
        carpeta = Path(tempfile.mkdtemp())
        q = mock.patch.object(M.diario, "CARPETA", carpeta)
        q.start()
        self.addCleanup(q.stop)
        q = mock.patch.object(M.aprendizaje, "EXPLORAR", 0.0)  # sin pruebas al azar (1 de cada 10)
        q.start()
        self.addCleanup(q.stop)
        ind = M.Indura({"nivel": "Chaos", "jugar": "Inteligente", "aprender": True, **valores})
        for nombre in ("log", "_stats"):
            q = mock.patch.object(ind, nombre, lambda *a, **k: None)
            q.start()
            self.addCleanup(q.stop)
        return ind

    def test_cada_pelea_se_apunta_en_el_diario(self):
        ind = self._con_diario({})
        ind._abrir_diario()
        self.assertEqual(ind.jugador.params, M.aprendizaje.DEFECTO, "sin peleas juega lo de siempre")
        ind._apuntar([Carta(0, tipo=T.NORMAL, rango=Rango.ORO)], 0)
        ind.diario.terminar("victoria")
        ind._abrir_diario()
        ind.al_terminar()  # se paro el bot a media pelea
        peleas = M.diario.leer("indura")
        self.assertEqual([p["resultado"] for p in peleas], ["abandonada", "victoria"])
        victoria = peleas[1]
        self.assertEqual((victoria["nivel"], victoria["jugar"], len(victoria["turnos"])), ("Chaos", "Inteligente", 1))
        self.assertEqual(victoria["config"], M.aprendizaje.DEFECTO)

    def test_aprende_por_separado_en_cada_nivel(self):
        ind = self._con_diario({})
        for nivel in ("Chaos", "Hell", "Chaos"):
            ind.valores["nivel"] = nivel
            ind._abrir_diario()
            ind.diario.terminar("victoria")
        self.assertEqual(len(ind.peleas_del_nivel()), 2)
        ind.valores["nivel"] = "Hell"
        self.assertEqual(len(ind.peleas_del_nivel()), 1)

    def test_mis_cartas_y_auto_no_cuentan_para_aprender(self):
        ind = self._con_diario({"jugar": "Mis cartas"})
        ind._abrir_diario()
        ind.diario.terminar("derrota")
        pelea = M.diario.leer("indura")[0]
        self.assertNotIn("config", pelea)
        self.assertEqual(M.aprendizaje.cifras([pelea]), {}, "solo el modo Inteligente tiene algo que ajustar")

    def test_equipo_de_mis_cartas(self):
        ind = self._con_diario({"jugar": "Mis cartas"})
        ind._abrir_diario()
        ind.estrategia = estrategias.Estrategia("Mi equipo", ["d", "b", "c", "a"], [])
        ind.equipo_usado = list(ind.estrategia.equipo)
        ind._cerrar_diario("victoria")
        self.assertEqual(ind.equipo_de_la_sesion(), ["a", "b", "c", "d"])
        self.assertEqual(M.diario.leer("indura")[0]["equipo"], ["a", "b", "c", "d"])

    def test_equipo_jugando_inteligente_por_las_cartas_vistas(self):
        ind = self._con_diario({})
        def carta(nombre):
            c = Carta(0, tipo=T.NORMAL, rango=Rango.ORO)
            c.nombre = nombre
            return c
        mano = [carta(f"{h}.skill_1") for h in ("enjin", "sho", "roxy")]
        for _ in range(M.VECES_HEROE):
            ind._contar_heroes(mano)
        self.assertIsNone(ind.equipo_de_la_sesion(), "con 3 heroes aun no se sabe el equipo")
        for _ in range(M.VECES_HEROE):
            ind._contar_heroes(mano + [carta("zanka.skill_2")])
        ind._contar_heroes([carta("mal_leida.skill_1")])  # una carta mal reconocida no entra
        self.assertEqual(ind.equipo_de_la_sesion(), ["enjin", "roxy", "sho", "zanka"])

    def test_carta_de_reserva(self):
        m = [Carta(0, tipo=T.NORMAL, rango=Rango.BRONCE), Carta(1, tipo=T.BLOQUEADA, rango=Rango.ORO),
             Carta(2, tipo=T.NORMAL, rango=Rango.PLATA)]
        self.assertEqual(estrategias.la_de_mas_rango(m).posicion, 2)
        self.assertIsNone(estrategias.la_de_mas_rango([Carta(0, tipo=T.SUELO)]))


class Botin(unittest.TestCase):
    def test_solo_se_deshacen_las_uniones_del_bot(self):
        catalogo = {
            "objeto_1": {"nombre": "A", "galeria": "g1", "unido_a": "objeto_2"},  # unida a mano
            "objeto_2": {"nombre": "B"},
            "objeto_3": {"nombre": "C", "galeria": "g1", "unido_a": "objeto_4", "unido_auto": True},
            "objeto_4": {"nombre": "D", "galeria": "g2"},
        }
        with mock.patch.object(botin, "cargar_catalogo", lambda: catalogo), \
             mock.patch.object(botin, "guardar_catalogo", lambda c: None), \
             mock.patch.object(recompensas, "reanalizar_pendientes") as reanalizar:
            self.assertEqual(recompensas.deshacer_uniones_malas(), 1)
            self.assertEqual(catalogo["objeto_1"]["unido_a"], "objeto_2")
            self.assertNotIn("unido_a", catalogo["objeto_3"])
            reanalizar.assert_called_once()

    def test_cantidad_con_los_digitos_del_juego(self):
        plantillas = botin._plantillas_digitos()

        def casilla(decena=None, unidad=None):
            c = np.full((botin.LADO, botin.LADO), 60, np.float32)
            for caja, hueco, d in ((botin.HUECO_DECENAS, "dec", decena), (botin.HUECO_UNIDADES, "uni", unidad)):
                if d is not None:
                    y1, y2, x1, x2 = caja
                    c[y1:y2, x1:x2] = plantillas[hueco][d][0]
            return cv2.cvtColor(c.astype(np.uint8), cv2.COLOR_GRAY2BGR)

        self.assertEqual(botin.leer_cantidad(casilla(unidad="5")), 5)
        self.assertEqual(botin.leer_cantidad(casilla("1", "5")), 15)
        self.assertEqual(botin.leer_cantidad(casilla("1", "0")), 10)
        self.assertEqual(botin.leer_cantidad(casilla()), 1)  # sin numero: una unidad

    def test_sin_boton_ok_no_hay_premios(self):
        # Las fotos de Indura en "HEART DESTROYED" daban trozos del fondo como objetos.
        pantalla = np.full((960, 554, 3), 40, np.uint8)
        with mock.patch.object(botin, "analizar") as analizar:
            self.assertTrue(recompensas._analizar(pantalla).get("sin_premios"))
            analizar.assert_not_called()

    def test_objeto_de_la_tabla_de_premios(self):
        self.assertIn("perros_pisos1a3", premios.donde_sale("fuerza_brok"))
        self.assertIn("fuerza_brok", premios.objetos_de("perros_pisos1a3"))
        self.assertEqual(premios.info("fuerza_brok").get("galeria"), "brokkr_s_strength")
        casilla = cv2.resize(vision.leer_imagen(premios.ICONOS / "fuerza_brok.png"), (botin.LADO, botin.LADO),
                             interpolation=cv2.INTER_AREA)
        icono = botin.icono(casilla)
        self.assertEqual(botin.en_premios(icono, premios.objetos_de("perros_pisos1a3")), "fuerza_brok")
        self.assertIsNone(botin.en_premios(icono, premios.objetos_de("indura")))  # no sale ahi


class Idiomas(unittest.TestCase):
    def test_busca_la_imagen_en_ingles_y_en_espanol(self):
        ingles = vision.leer_imagen(IMAGENES / "start.png")
        espanol = 255 - ingles  # un "boton en espanol" de prueba
        with tempfile.TemporaryDirectory() as carpeta:
            carpeta = Path(carpeta)
            (carpeta / "es").mkdir()
            cv2.imwrite(str(carpeta / "start.png"), ingles)
            cv2.imwrite(str(carpeta / "es" / "start.png"), espanol)
            with mock.patch.object(vision, "IMAGENES", carpeta):
                p = vision.Plantilla("start.png")
                self.assertEqual(len(p.imagenes), 2)
                pantalla = np.zeros((300, 300, 3), np.uint8)
                h, w = ingles.shape[:2]
                for boton in (espanol, ingles):
                    pantalla[50:50 + h, 60:60 + w] = boton
                    self.assertTrue(p.esta(pantalla, 0.9))
                (carpeta / "es" / "start.png").unlink()
                self.assertEqual(len(vision.Plantilla("start.png").imagenes), 1)


class Premios(unittest.TestCase):
    def test_todas_las_tablas_tienen_sus_iconos(self):
        from lumen.modos.catalogo import CATALOGO

        destinos = [d.id for c in CATALOGO if c.grupo != "Fuerte Solgres" for d in c.destinos]
        self.assertEqual(len(destinos), 15)
        for d in destinos:
            with self.subTest(destino=d):
                lista = premios.de(d)
                self.assertTrue(lista, "sin tabla de premios")
                for p in lista:
                    self.assertTrue(p.icono.is_file(), p.objeto)

    def test_juntar_lineas_y_garantizados(self):
        lista = premios.de("perros_piso4")
        self.assertEqual([p.texto_prob for p in lista[:2]], ["Siempre", "Siempre"])
        garra = next(p for p in lista if p.objeto == "garra_skoll_hati" and not p.siempre)
        self.assertEqual((garra.texto_cantidad, garra.texto_prob), ("×1–4", "49 %"))


class EquipoMasRapido(unittest.TestCase):
    def setUp(self):
        entorno.app_qt()
        from lumen.gui.paginas import equipos as E

        self.E = E
        self.base = {"perros_piso4": [
            {"nombre": "Lento", "bot": True, "minutos": 4, "personajes": ["a", "b"]},
            {"nombre": "Rapido", "bot": True, "minutos": 2.5, "personajes": ["c", "d"]},
            {"nombre": "Sin bot", "minutos": 1, "personajes": ["e", "f"]},
            {"nombre": "Sin medir", "bot": True, "personajes": ["g", "h"]},
        ]}
        self.medido = {}
        for nombre, valor in (("cargar_equipos", lambda: self.base), ("medidas", lambda clave: self.medido)):
            parche = mock.patch.object(E, nombre, valor)
            parche.start()
            self.addCleanup(parche.stop)

    def test_el_de_menos_minutos_que_el_bot_juega(self):
        r = self.E.mas_rapido("perros_piso4")
        self.assertEqual((r["datos"]["nombre"], r["minutos"], r["fuente"]), ("Rapido", 2.5, "pruebas"))

    def test_lo_medido_en_esta_pc_manda(self):
        self.medido[frozenset(["a", "b"])] = {"victorias": 10, "derrotas": 0, "reinicios": 0, "por_hora": 30.0}
        r = self.E.mas_rapido("perros_piso4")
        self.assertEqual((r["datos"]["nombre"], r["minutos"], r["fuente"]), ("Lento", 2.0, "tuyo"))
        self.medido[frozenset(["a", "b"])]["victorias"] = 2  # pocas peleas: cuenta igual (lo pidio el usuario)
        r = self.E.mas_rapido("perros_piso4")
        self.assertEqual((r["datos"]["nombre"], r["fuente"], r["peleas"]), ("Lento", "tuyo", 2))

    def test_tu_equipo_aunque_sea_el_unico(self):
        self.base = {}
        self.medido[frozenset(["equipo:Farm.Oro"])] = {"victorias": 1, "derrotas": 0, "reinicios": 1, "por_hora": 40.0}
        r = self.E.mas_rapido("monedas_sa")
        self.assertEqual((r["datos"]["nombre"], r["minutos"], r["peleas"]), ("Farm.Oro", 1.5, 2))

    def test_texto(self):
        self.assertEqual(self.E.texto_minutos(2.5), "2,5 min por victoria")
        self.assertEqual(self.E.texto_minutos(3), "3 min por victoria")


class Informe(unittest.TestCase):
    def test_error_con_donde_y_ultimos_pasos(self):
        from lumen import informe

        for i in range(20):
            informe.anotar(f"paso {i}", "info")
        modo = type("M", (), {"nombre": "Rata · Floor 1-3", "id": "rata_pisos1a3", "estado": "elegir_piso"})()
        try:
            informe._tiempo("no es un numero")  # un error que salta dentro de lumen/
        except ValueError as error:  # (assertRaises borra la traza, y aqui hace falta)
            texto = informe.texto_error(modo, error)
            self.assertIn("informe.py:", informe.resumen_error(error))
        self.assertIn("ERROR", texto)
        self.assertIn("estado: elegir_piso", texto)
        self.assertIn("En: ", texto)
        self.assertIn("paso 19", texto)
        self.assertNotIn("paso 7", texto, "solo los ultimos pasos")

    def test_texto_de_la_prueba(self):
        from lumen import informe

        texto = informe.texto_prueba([
            {"nombre": "Pájaro", "resultado": "ok", "victorias": 1, "segundos": 185, "motivo": ""},
            {"nombre": "Ciervo", "resultado": "fallo", "victorias": 0, "segundos": 40, "motivo": "ERROR: KeyError"},
            {"nombre": "Indura", "resultado": "no_empezo", "victorias": 0, "segundos": 0, "motivo": "no empezó: Juego cerrado"},
        ])
        lineas = texto.splitlines()
        self.assertEqual(lineas[1], "✓ Pájaro · 1 victoria · 3:05")
        self.assertEqual(lineas[2], "✗ Ciervo · 0 victorias · 0:40 · ERROR: KeyError")
        self.assertEqual(lineas[3], "– Indura · no empezó: Juego cerrado")
        self.assertEqual(lineas[4], "Resultado: 1 de 3 bien · 3:45")


class CanalSecreto(unittest.TestCase):
    def test_nombres_largos_y_distintos(self):
        entorno.app_qt()
        from lumen.gui.paginas.ajustes import MINIMO_CANAL, canal_secreto

        nombres = {canal_secreto() for _ in range(50)}
        self.assertEqual(len(nombres), 50)
        for n in nombres:
            self.assertRegex(n, r"^lumen-[a-z0-9]{16}$")
            self.assertGreaterEqual(len(n), MINIMO_CANAL)


class Aprender(unittest.TestCase):
    def test_reconoce_igual_que_comparar_todo(self):
        from lumen.modos.aprender import IndiceCartas

        ind = IndiceCartas()
        rng = random.Random(7)
        np.random.seed(7)

        def carta_de(img):
            fondo = np.random.randint(20, 60, (123, 57, 3), np.uint8)
            y, x = rng.randint(20, 45), rng.randint(4, 10)
            fondo[y:y + img.shape[0], x:x + img.shape[1]] = cv2.convertScaleAbs(img, alpha=rng.uniform(0.9, 1.1), beta=rng.uniform(-12, 12))
            return np.clip(fondo + np.random.normal(0, 5, fondo.shape), 0, 255).astype(np.uint8)

        def gemelos(img):
            """Heroes con esa misma imagen de carta: las versiones de color de un heroe suelen compartir
            la ulti (Griamore verde y azul, Ban de tres colores... 141 pares en la base). Con solo esa
            carta no se puede saber cual es; el equipo se reconoce por todas las cartas de la mano."""
            return {p for p, _, t, _ in ind.plantillas
                    if t.imagenes[0].shape == img.shape and float(cv2.absdiff(t.imagenes[0], img).mean()) < 1}

        for i in rng.sample(range(len(ind.plantillas)), 25):
            pid, cid, plantilla, _ = ind.plantillas[i]
            with self.subTest(carta=f"{pid}.{cid}"):
                carta = Carta(0, imagen=carta_de(plantilla.imagenes[0]), tipo=T.NORMAL)
                self.assertIn(ind.heroe_de(carta), gemelos(plantilla.imagenes[0]) | {pid})


if __name__ == "__main__":
    unittest.main()


class EquipoMasRapido2(unittest.TestCase):
    def test_equipo_de_fuerte_solgres_por_su_nombre(self):
        from lumen.modos import fuerte_solgres as F

        m = F.MonedasSA({})
        lineas = [("Clock Tower of Eternity", (0, 0, 1, 1)), ("- 3rd Floor -", (0, 0, 1, 1)),
                  ("Farm.Oro", (0, 0, 1, 1)), ("Team List 15/15", (0, 0, 1, 1))]
        with mock.patch("lumen.ocr.disponible", lambda: True), mock.patch("lumen.ocr.lineas_con_posicion", lambda img: lineas):
            m.leer_equipo(np.zeros((940, 550, 3), np.uint8))
        self.assertEqual(m.equipo_de_la_sesion(), ["equipo:Farm.Oro"])

    def test_equipo_de_la_lista_por_su_nombre_del_juego(self):
        from lumen.gui.paginas import equipos as E

        lista = {"monedas_sa": [{"nombre": "Escalin", "nombre_juego": "Farm.Oro", "personajes": ["a", "b", "c", "d"]}]}
        medido = {frozenset(["equipo:Farm.Oro"]): {"victorias": 3, "derrotas": 0, "reinicios": 1, "por_hora": 30.0}}
        with mock.patch.object(E, "cargar_equipos", lambda: lista), mock.patch.object(E, "medidas", lambda c: medido):
            r = E.mas_rapido("monedas_sa")
        self.assertEqual((r["datos"]["nombre"], r["datos"]["personajes"], r["minutos"]), ("Escalin", ["a", "b", "c", "d"], 2.0))


class PublicarEquipos(unittest.TestCase):
    NUEVO = {"nombre": "Prueba: rara", "nivel": "bueno", "personajes": ["a", "b", "c", "d"], "notas": "Uno.\nDos."}

    def test_insertar_conserva_el_archivo_y_los_comentarios(self):
        import yaml

        from lumen import publicar as PE
        from lumen.gui.paginas.equipos import ARCHIVO

        texto = ARCHIVO.read_text(encoding="utf-8")
        nuevo = PE.insertar(PE.insertar(texto, "pajaro_piso4", self.NUEVO), "contenido_nuevo", self.NUEVO)
        antes, despues = yaml.safe_load(texto), yaml.safe_load(nuevo)
        self.assertEqual(despues["pajaro_piso4"][:-1], antes["pajaro_piso4"])
        self.assertEqual(despues["pajaro_piso4"][-1]["nombre"], "Prueba: rara")
        self.assertEqual(despues["contenido_nuevo"][0]["personajes"], ["a", "b", "c", "d"])
        self.assertEqual({k: v for k, v in despues.items() if k not in ("pajaro_piso4", "contenido_nuevo")},
                         {k: v for k, v in antes.items() if k != "pajaro_piso4"})
        self.assertTrue(nuevo.startswith(texto.splitlines()[0]), "los comentarios del principio siguen")

    def test_pendientes_solo_los_que_no_estan(self):
        from lumen import publicar as PE

        base = {"x": [{"nombre": "Viejo", "personajes": ["d", "c", "b", "a"]}]}
        propios = {"x": [self.NUEVO, {"nombre": "Otro", "personajes": ["e", "f", "g", "h"]}], "y": [self.NUEVO]}
        faltan = PE.equipos_pendientes(base, propios)
        self.assertEqual([d["nombre"] for d in faltan["x"]], ["Otro"], "mismos personajes = ya publicado")
        self.assertEqual(len(faltan["y"]), 1)

    def test_publicar_sube_a_la_rama_sin_tocar_la_carpeta(self):
        """Con un repositorio de prueba: sube el equipo, el heroe nuevo (con sus imagenes) y los retratos una vez;
        la segunda vez no hay nada nuevo."""
        import subprocess

        import yaml

        from lumen import actualizador, publicar as PE

        def git(*args, cwd):
            subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)

        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            remoto, local = d / "remoto.git", d / "local"
            git("init", "--bare", "-b", "master", str(remoto), cwd=d)
            git("clone", str(remoto), str(local), cwd=d)
            (local / "lumen" / "datos").mkdir(parents=True)
            (local / PE.EQUIPOS_EN_REPO).write_text("# equipos\nx:\n  - nombre: Viejo\n    personajes: [a, b, c, e]\n",
                                                   encoding="utf-8")
            (local / PE.HEROES_EN_REPO).write_text("# heroes\n\nodin:\n  nombre: Odin\n  color: claro\n", encoding="utf-8")
            git("add", ".", cwd=local)
            git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base", cwd=local)
            git("push", "-q", "origin", "HEAD:master", cwd=local)
            mias = d / "personajes"  # personajes/<id>/ de este PC
            for pid, nombres in (("violet_rojo", ("icono.png", "skill_1_ficha.png", "icono_anterior.png")),
                                 ("odin", ("cara_artwork.jpg",))):
                (mias / pid).mkdir(parents=True)
                for n in nombres:
                    (mias / pid / n).write_bytes(n.encode())
            heroes = {"violet_rojo": {"nombre": "Violet", "color": "rojo", "tengo": True,
                                      "cartas": {"skill_1": {"descripcion": "Un objetivo"}}},
                      "odin": {"tengo": True}}
            mio = PE.Local(equipos={"x": [self.NUEVO]}, heroes=heroes, carpeta=mias,
                           claves={"violet_rojo": "[Cumbre] Violet"})
            with mock.patch.object(actualizador, "RAIZ", local), mock.patch.object(PE, "COPIA", d / "copia"),                     mock.patch.dict("os.environ", {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                                                   "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}):
                hecho = PE.publicar(mio)
                self.assertEqual((hecho.equipos, hecho.heroes, hecho.retratos), (1, 1, 1))
                self.assertFalse(PE.publicar(mio), "ya estaba todo publicado")

            def remoto_(ruta):
                return subprocess.run(["git", "show", f"master:{ruta}"], cwd=remoto, capture_output=True, text=True,
                                      check=True).stdout

            self.assertEqual([e["nombre"] for e in yaml.safe_load(remoto_("lumen/datos/equipos.yaml"))["x"]],
                             ["Viejo", "Prueba: rara"])
            base = yaml.safe_load(remoto_("lumen/datos/personajes.yaml"))
            self.assertEqual(base["violet_rojo"]["clave"], "[Cumbre] Violet")
            self.assertNotIn("tengo", base["violet_rojo"], "lo que tiene cada uno no va a la base")
            self.assertEqual(remoto_("assets/personajes/violet_rojo/skill_1_ficha.png"), "skill_1_ficha.png")
            self.assertEqual(remoto_("assets/personajes/odin/cara_artwork.jpg"), "cara_artwork.jpg")
            archivos = subprocess.run(["git", "ls-tree", "-r", "--name-only", "master"], cwd=remoto, capture_output=True,
                                      text=True, check=True).stdout
            self.assertNotIn("_anterior", archivos, "las copias de deshacer no se publican")
            self.assertNotIn("Prueba", (local / PE.EQUIPOS_EN_REPO).read_text(encoding="utf-8"), "la carpeta no se toca")
            self.assertFalse((d / "copia").exists(), "la copia temporal se borra")


class PaginaPersonajesRapida(unittest.TestCase):
    def test_tarjetas_con_padre_e_imagenes_al_verse(self):
        entorno.app_qt()
        from lumen import personajes as P
        from lumen.gui.paginas import personajes as G

        with tempfile.TemporaryDirectory() as d, mock.patch.object(P, "CARPETA", Path(d)), \
                mock.patch.object(P, "USUARIO", Path(d) / "usuario.yaml"):
            pagina = G.PaginaPersonajes(mock.Mock())
            self.assertTrue(pagina.tarjetas)
            for t in pagina.tarjetas.values():
                self.assertIsNotNone(t.parentWidget(), "sin padre seria una ventana suelta")
                self.assertFalse(t.cargada, "sin mostrarse no se lee ninguna imagen")
            antes = dict(pagina.tarjetas)
            pagina.al_mostrar()
            self.assertTrue(all(pagina.tarjetas[k] is antes[k] for k in antes), "se reutilizan entre visitas")

    def test_marcar_todos_los_que_se_ven(self):
        """Lo pidio un probador: con ~365 personajes, marcar todos y quitar los que faltan es mas rapido."""
        entorno.app_qt()
        from lumen import personajes as P
        from lumen.gui.paginas import personajes as G

        with tempfile.TemporaryDirectory() as d, mock.patch.object(P, "CARPETA", Path(d)), \
                mock.patch.object(P, "USUARIO", Path(d) / "usuario.yaml"):
            pagina = G.PaginaPersonajes(mock.Mock())
            self.assertFalse(any(p.tengo for p in pagina.biblioteca.values()), "un jugador nuevo empieza sin ninguno")
            rojo = next(b for b in pagina.atributos.buttons() if b.property("color") == "rojo")
            rojo.setChecked(True)  # solo se ven los rojos
            pagina._pintar()
            rojos = pagina.visibles()
            self.assertTrue(rojos)
            with mock.patch.object(G.QMessageBox, "question", return_value=G.QMessageBox.Yes):
                pagina._marcar_visibles(True)
            guardado = P.cargar()
            self.assertEqual({p for p, pj in guardado.items() if pj.tengo}, set(rojos), "solo los que se veian")
            pagina._cambiar(rojos[0], False)  # y se quita a mano el que falta
            self.assertFalse(P.cargar()[rojos[0]].tengo)
            with mock.patch.object(G.QMessageBox, "question", return_value=G.QMessageBox.No):
                pagina._marcar_visibles(False)
            self.assertTrue(P.cargar()[rojos[1]].tengo, "si dice que no, no cambia nada")
            with mock.patch.object(G.QMessageBox, "question", return_value=G.QMessageBox.Yes):
                pagina._marcar_visibles(False)
            self.assertFalse(any(pj.tengo for pj in P.cargar().values()))


class PrecargaCartas(unittest.TestCase):
    """PC lento de un probador (0.16.0): la primera carta tardo casi 2 min en cargar el indice de cartas."""

    def test_se_carga_en_segundo_plano_y_la_jugada_la_espera(self):
        from lumen import inteligencia, valor_cartas
        from lumen.modos import aprender

        cargas = []

        class IndiceLento:
            def __init__(self):
                time.sleep(0.3)
                cargas.append(1)

            def carta_de(self, carta):
                return "heroe.skill_1"

        with mock.patch.object(aprender, "IndiceCartas", IndiceLento), \
                mock.patch.object(valor_cartas, "Tasador", lambda enemigos: object()):
            jugador = inteligencia.Jugador()
            inicio = time.perf_counter()
            jugador.precargar()
            self.assertLess(time.perf_counter() - inicio, 0.1, "precargar no bloquea")
            self.assertEqual(jugador._identificar(Carta(0, tipo=T.NORMAL, rango=Rango.ORO)), "heroe.skill_1")
            self.assertEqual(cargas, [1], "la jugada espera a la carga que ya iba y no carga otra vez")

    def test_el_modo_precarga_al_empezar_a_correr(self):
        from lumen.modos import bestias_pisos1a3 as B

        modo = next(m for m in B.__dict__.values() if isinstance(m, type) and issubclass(m, B.BestiaPisos1a3)
                    and m is not B.BestiaPisos1a3)({"jugar": "Inteligente"})
        with mock.patch.object(modo.estrategia.jugador, "precargar") as precargar:
            modo.al_empezar()
        precargar.assert_called_once()


class CantidadesSobreFondoClaro(unittest.TestCase):
    """Cubo amarillo: el "1" de las decenas casi no se ve sobre el fondo claro (prueba del usuario, 2026-11-09)."""

    def leer(self, nombre):
        return botin.leer_cantidad(cv2.imread(str(Path(__file__).with_name(f"{nombre}.png"))))

    def test_diez_y_quince_amarillos(self):
        self.assertEqual(self.leer("cubo_amarillo_10"), 10, "se leia 1")
        self.assertEqual(self.leer("cubo_amarillo_15"), 15, "se leia 5")
        self.assertEqual(self.leer("objeto_4"), 4, "los de una cifra siguen igual")

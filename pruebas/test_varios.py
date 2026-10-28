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
        self.medido[frozenset(["a", "b"])]["victorias"] = 2  # pocas peleas: no cuenta
        self.assertEqual(self.E.mas_rapido("perros_piso4")["datos"]["nombre"], "Rapido")

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

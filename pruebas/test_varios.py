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

        for i in rng.sample(range(len(ind.plantillas)), 25):
            pid, cid, plantilla, _ = ind.plantillas[i]
            with self.subTest(carta=f"{pid}.{cid}"):
                carta = Carta(0, imagen=carta_de(plantilla.imagenes[0]), tipo=T.NORMAL)
                self.assertEqual(ind.heroe_de(carta), pid)


if __name__ == "__main__":
    unittest.main()

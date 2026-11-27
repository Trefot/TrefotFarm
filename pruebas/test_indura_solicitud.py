"""Indura, Enviar solicitud: la sala propia, invitar a Favoritos, 3 cartas y rendirse (capturas del 2026-11-27)."""
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

import entorno  # noqa: F401
from lumen.modos import indura as M
from lumen.vision import leer_imagen

CARPETA = Path(__file__).with_name("indura_sala")
F = {n: leer_imagen(CARPETA / f"{n}.jpg") for n in ("menu_death_match", "niveles", "sala_vacia", "invitar_favoritos",
                                                     "invitar_amigos", "sala_con_amigo", "pelea", "rendirse",
                                                     "despues_de_salir")}
NEGRA = np.zeros((940, 550, 3), np.uint8)


class Reconocer(unittest.TestCase):
    """Cada imagen se ve en su pantalla y no en las demas."""

    CASOS = {
        "DM_INDURA": ("menu_death_match", "despues_de_salir"),
        "NIVELES_INDURA": ("niveles",),
        "SALA_INVITAR": ("sala_vacia",),
        "AMIGO_LISTO": ("sala_con_amigo",),
        "INVITAR_VENTANA": ("invitar_favoritos", "invitar_amigos"),
        "RENDIRSE_TEXTO": ("rendirse",),
    }
    UMBRAL = {"DM_INDURA": 0.75, "NIVELES_INDURA": 0.8, "SALA_INVITAR": 0.8, "AMIGO_LISTO": 0.75,
              "INVITAR_VENTANA": 0.85, "RENDIRSE_TEXTO": 0.8}

    def test_cada_una_en_su_pantalla(self):
        for nombre, donde in self.CASOS.items():
            plantilla, umbral = getattr(M, nombre), self.UMBRAL[nombre]
            for pantalla, img in F.items():
                with self.subTest(nombre=nombre, pantalla=pantalla):
                    self.assertEqual(plantilla.esta(img, umbral), pantalla in donde)

    def test_invite_all_solo_en_amarillo(self):
        self.assertTrue(M.INVITAR_TODOS.esta(F["invitar_amigos"], 0.9))
        self.assertFalse(M.INVITAR_TODOS.esta(F["invitar_favoritos"], 0.9))  # gris: nadie a quien invitar

    def test_nivel_y_boton_de_rendirse(self):
        self.assertTrue(M.NIVEL_SALA["Chaos"].esta(F["niveles"], 0.75))
        self.assertTrue(M.RENDIRSE.esta(F["pelea"], 0.8))
        self.assertTrue(M.RENDIRSE_OK.esta(F["rendirse"], 0.8))
        self.assertTrue(M.AUTO.esta(F["pelea"], 0.8))
        self.assertEqual(M.cartas.casillas_libres_demonio(F["pelea"]), 3)


class Flujo(unittest.TestCase):
    def setUp(self):
        self.m = M.Indura({"partidas": M.ENVIAR, "nivel": "Chaos", "victorias": 0, "jugar": "Mis cartas",
                           "espera": "9.3", "minutos_sin_invitacion": 20})
        self.m.log = lambda *a, **k: None
        self.clics = []
        self.siguiente = []
        self.m.capturar = lambda: (self.siguiente.pop(0) if self.siguiente else NEGRA, (0, 0))

        def clic_si(plantilla, p, o, umbral=0.7, punto=None, espera=0.25):
            if plantilla.esta(p, umbral):
                self.clics.append(plantilla.nombre)
                return True
            return False

        for parche in (mock.patch.object(self.m, "clic_si", side_effect=clic_si),
                       mock.patch.object(M.entrada, "clic", side_effect=lambda r, o, espera=0: self.clics.append(r))):
            parche.start()
            self.addCleanup(parche.stop)

    def test_opciones_solo_en_indura(self):
        self.assertIn("partidas", [o.clave for o in M.Indura.opciones])
        self.assertNotIn("partidas", [o.clave for o in M.DemonioRojo.opciones])
        self.assertEqual(M.Indura({"partidas": M.ENVIAR}).estado_inicial(), "abrir_sala")
        self.assertTrue(M.Indura({"partidas": M.AMIGOS_ANTES}).de_amigos)  # el nombre de la 0.46.0

    def test_abre_la_sala(self):
        self.assertIsNone(self.m.abrir_sala(F["menu_death_match"], (0, 0)))
        self.assertEqual(self.clics[-1], "dm_indura")
        self.assertIsNone(self.m.abrir_sala(F["niveles"], (0, 0)))
        self.assertEqual(self.clics[-1], "sala_chaos")
        self.assertEqual(self.m.abrir_sala(F["sala_vacia"], (0, 0)), "sala_propia")

    def test_invita_a_favoritos_y_cierra(self):
        self.m.abrir_sala(F["sala_vacia"], (0, 0))
        self.assertIsNone(self.m.sala_propia(F["sala_vacia"], (0, 0)))
        self.assertEqual(self.clics[-1], "sala_invitar")
        self.siguiente = [F["invitar_amigos"]]  # tras tocar Favoritos (aqui, con Invite All amarillo)
        self.assertIsNone(self.m.sala_propia(F["invitar_favoritos"], (0, 0)))
        self.assertIn(M.PESTANA_FAVORITOS, self.clics)
        self.assertIn("invitar_todos", self.clics)
        self.assertEqual(self.clics[-1], "invitar_cerrar")

    def test_empieza_cuando_la_otra_cuenta_esta_lista(self):
        self.m.abrir_sala(F["sala_vacia"], (0, 0))
        self.assertIsNone(self.m.sala_propia(F["sala_con_amigo"], (0, 0)))
        self.assertEqual(self.clics[-1], "sala_preparacion")
        self.m.sala_propia(F["sala_con_amigo"], (0, 0))  # no lo vuelve a pulsar (lo quitaria)
        self.assertEqual(self.clics.count("sala_preparacion"), 1)
        self.assertEqual(self.m.sala_propia(F["pelea"], (0, 0)), "pelea_corta")

    def test_tres_cartas_y_se_rinde(self):
        self.m._empezar_pelea_corta()
        with mock.patch.object(M.cartas, "casillas_libres_demonio", side_effect=[3, 2, 1, 0]), \
                mock.patch.object(M.time, "time", side_effect=[0, 5, 10, 15, 20, 25, 30]):
            for _ in range(3):
                self.m.pelea_corta(F["pelea"], (0, 0))
            self.assertEqual(self.m.lanzadas, 2)
            self.assertNotIn("pelea_rendirse", self.clics)
            self.m.pelea_corta(F["pelea"], (0, 0))
        self.assertEqual(self.m.lanzadas, 3)
        self.assertEqual(self.clics[-1], "pelea_rendirse")
        self.assertNotIn("auto", self.clics)
        self.assertEqual(self.m.pelea_corta(F["rendirse"], (0, 0)), "abrir_sala")
        self.assertEqual(self.clics[-1], "rendirse_ok")
        self.assertEqual(self.m.victorias, 1)


if __name__ == "__main__":
    unittest.main()

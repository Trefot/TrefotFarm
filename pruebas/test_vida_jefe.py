"""Vida del jefe: fotos sacadas del video del usuario (ciervo Floor 4, 2026-11-13)."""
import unittest
from pathlib import Path

import cv2
import numpy as np

import entorno  # noqa: F401
from lumen import vida_jefe as V

FOTOS = Path(__file__).with_name("vida_jefe")


def foto(nombre):
    img = cv2.imread(str(FOTOS / f"ciervo4_{nombre}.png"))
    assert img is not None, nombre
    return img


class LeerVida(unittest.TestCase):
    def test_cada_fase_y_lo_que_le_queda(self):
        for nombre, capa, cuanto in (("verde_100", "verde", 100), ("verde_40", "verde", 40), ("azul_9", "azul", 9),
                                     ("morado_39", "morado", 39), ("rojo_89", "rojo", 89)):
            with self.subTest(nombre):
                vida = V.leer(foto(nombre))
                self.assertIsNotNone(vida)
                self.assertEqual(vida.capa, capa)
                self.assertAlmostEqual(vida.por_ciento, cuanto, delta=3)

    def test_casi_vacia_lee_la_capa_de_esta_fase(self):
        """Revision 2026-11-23: con la capa casi vacia (1-5 px) la mayoria de las primeras columnas ya son de la fase
        siguiente; se leia esa (llena) y el bot pasaba de fase un turno antes. Foto real del rojo al 89 % con los
        primeros pixeles de la foto real del morado encima."""
        x1, y1, x2, y2 = V.BARRA
        for px in (3, 5):
            with self.subTest(pixeles=px):
                img = foto("rojo_89").copy()
                img[y1:y2, x1:x1 + px] = foto("morado_39")[y1:y2, x1:x1 + px]
                vida = V.leer(img)
                self.assertEqual(vida.capa, "morado")
                self.assertLess(vida.por_ciento, 5)
        self.assertEqual(V.leer(foto("rojo_89")).capa, "rojo", "sin morado: sigue siendo rojo")

    def test_al_morir_la_barra_queda_vacia(self):
        self.assertEqual(V.leer(foto("vacia")), V.Vida(V.VACIA, 0.0))

    def test_pantalla_negra_no_es_barra_vacia(self):
        self.assertIsNone(V.leer(foto("negro")))
        self.assertIsNone(V.leer(np.zeros((940, 550, 3), np.uint8)))
        self.assertIsNone(V.leer(None))

    def test_texto(self):
        self.assertEqual(V.Vida("azul", 0.47).texto(), "azul 47 %")


class EnElRegistro(unittest.TestCase):
    def test_el_turno_anota_la_vida_del_jefe(self):
        from unittest import mock
        from lumen.control import control
        from lumen.modos import MODOS
        control.reiniciar()
        m = MODOS["ciervo_piso4"]({"victorias": 0, "extra": 0, "pociones": True, "max_pociones": 0})
        mensajes = []
        m.log = lambda texto, *a, **k: mensajes.append(texto)
        p = np.zeros((940, 550, 3), np.uint8)
        p[:130] = foto("azul_9")
        with mock.patch.object(m, "_detectar_fase", return_value=2), \
             mock.patch.object(m, "_reiniciar_por_bloqueo", return_value=False), \
             mock.patch.object(m, "_hay_talento", return_value=False), \
             mock.patch.object(m, "_jugar_turno", return_value=None):
            m._empezar_turno(p, 4)
        self.assertEqual(m.vida_jefe.capa, "azul")
        self.assertTrue(any("Vida del jefe: azul 9 %" in t for t in mensajes), mensajes)

    def test_los_lobos_no_la_leen(self):
        from lumen.modos import MODOS
        self.assertFalse(MODOS["perros_piso4"].leer_vida_jefe)

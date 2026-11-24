"""Detector propio de huecos vacios de la mano (lumen/huecos.py), en lugar del modelo antiguo."""
import unittest
from pathlib import Path

import cv2

import entorno  # noqa: F401
from lumen import cartas as C, huecos

AQUI = Path(__file__).parent


def tipos(nombre):
    p = cv2.imread(str(AQUI / nombre))
    assert p is not None, nombre
    return "".join("S" if c.tipo == C.TipoCarta.SUELO else "c" for c in C.leer_mano(p))


class Huecos(unittest.TestCase):
    def test_mano_con_tres_huecos(self):
        """Prueba de 5 victorias (perros Floor 4): casillas 1, 2 y 8 vacias, 5 cartas en medio."""
        self.assertEqual(tipos("mano_con_huecos.png"), "SScccccS")

    def test_mano_llena_de_monedas_sa(self):
        self.assertEqual(tipos("botin_sa/pelea.png"), "cccccccc")

    def test_ya_no_hay_modelo_antiguo(self):
        self.assertFalse((huecos.ARCHIVO.parent / "ground_cards_predictor.svc").exists())
        self.assertTrue(huecos.ARCHIVO.is_file())


if __name__ == "__main__":
    unittest.main()

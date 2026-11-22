"""Monedas SA: la foto del botin de cada vuelta (capturas del usuario, 2026-11-22: el modo no guardaba ninguna)."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cv2

import entorno  # noqa: F401
from lumen import botin
from lumen.modos import fuerte_solgres as F

FOTOS = Path(__file__).with_name("botin_sa")


def foto(nombre):
    img = cv2.imread(str(FOTOS / f"{nombre}.png"))
    assert img is not None, nombre
    return img


class LeerBotin(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        raiz = Path(tmp.name)
        for nombre, valor in (("CARPETA", raiz / "objetos"), ("CATALOGO", raiz / "catalogo.yaml"),
                              ("CATALOGO_BASE", raiz / "base.yaml"), ("GALERIA", raiz / "galeria.yaml")):
            p = mock.patch.object(botin, nombre, valor)
            p.start()
            self.addCleanup(p.stop)

    def test_victoria_limpia_dos_monedas_y_el_oro(self):
        for nombre in ("victoria_limpia", "victoria_fin_cuenta"):
            with self.subTest(nombre):
                r = botin.analizar(foto(nombre), modo="monedas_sa")
                self.assertEqual(r["objetos"], {"galeria_super_awakening_coin": 2})
                self.assertEqual(r["oro"], 12000, '"12,000 (+6000)": solo el primer numero')
                self.assertFalse(r["lectura_incompleta"])

    def test_oscurecida_no_inventa(self):
        r = botin.analizar(foto("victoria_oscura"), modo="monedas_sa")
        self.assertEqual(r["objetos"], {})


class FotoDeCadaVuelta(unittest.TestCase):
    def setUp(self):
        self.m = F.MonedasSA({"victorias": 0, "pociones": True, "max_pociones": 0, "cofre": "Bronce",
                              "segundos_cofre": 12})
        self.m.log = lambda *a, **k: None
        self.fotos = []
        p = mock.patch.object(self.m, "guardar_recompensa", side_effect=lambda pant, v, **k: self.fotos.append(v))
        p.start()
        self.addCleanup(p.stop)

    def test_una_foto_por_vuelta_en_el_momento_limpio(self):
        for nombre in ("pelea", "victoria_limpia", "victoria_oscura", "victoria_oscura", "victoria_fin_cuenta",
                       "pelea", "victoria_oscura", "victoria_fin_cuenta", "pelea"):
            self.m._foto_botin(foto(nombre))
        self.assertEqual(self.fotos, [1, 1], "una por vuelta; la segunda, al final de la cuenta atras")

    def test_ni_oscurecida_ni_resumen_final(self):
        for nombre in ("victoria_oscura", "repeticion_terminada"):
            self.m._foto_botin(foto(nombre))
        self.assertEqual(self.fotos, [])


if __name__ == "__main__":
    unittest.main()

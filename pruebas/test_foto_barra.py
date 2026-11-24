"""Lobos Floor 4: su barra de vida aun no esta medida, asi que Lumen guarda solo la parte de arriba de cada turno
(el usuario, 2026-11-24: "la barra de vida se captura sola?")."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

import entorno  # noqa: F401  (antes que lumen)

from lumen.modos import MODOS
from lumen.modos import perros_piso4


class FotoBarra(unittest.TestCase):
    def modo(self):
        m = MODOS["perros_piso4"]({"victorias": 0, "extra": 0, "pociones": True, "max_pociones": 0})
        m.log = lambda *a, **k: None
        return m

    def test_guarda_la_tira_de_arriba_con_fase_y_turno(self):
        m = self.modo()
        m.fase, m.turno_fase = 2, 0
        with tempfile.TemporaryDirectory() as d, mock.patch.object(perros_piso4, "RAIZ", Path(d)):
            m._foto_barra(np.zeros((940, 550, 3), np.uint8))
            fotos = list((Path(d) / "capturas" / "vida_jefe").rglob("*.png"))
            self.assertEqual(len(fotos), 1)
            self.assertTrue(fotos[0].name.endswith("_f2t1.png"))

    def test_no_pasa_del_maximo(self):
        m = self.modo()
        with tempfile.TemporaryDirectory() as d, mock.patch.object(perros_piso4, "RAIZ", Path(d)), \
                mock.patch.object(perros_piso4, "FOTOS_BARRA_MAXIMAS", 0):
            m._foto_barra(np.zeros((940, 550, 3), np.uint8))
            self.assertEqual(list(Path(d).rglob("*.png")), [])


if __name__ == "__main__":
    unittest.main()

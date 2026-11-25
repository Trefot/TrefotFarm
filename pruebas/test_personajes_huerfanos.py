"""Un "tengo" suelto en usuario.yaml de un heroe que ya no esta en la base no sale como ficha sin nombre
(la Ellatte verde duplicada, 2026-11-24)."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

import entorno  # noqa: F401  (antes que lumen)

from lumen import personajes as P


class Huerfanos(unittest.TestCase):
    def test_tengo_suelto_no_crea_ficha(self):
        with tempfile.TemporaryDirectory() as d:
            usuario = Path(d) / "usuario.yaml"
            usuario.write_text(yaml.safe_dump({"celestial_ellatte_verde_2": {"tengo": True},
                                               "mi_heroe": {"nombre": "Mio", "color": "rojo", "tengo": True}}),
                               encoding="utf-8")
            with mock.patch.object(P, "USUARIO", usuario), mock.patch.object(P, "_primera_vez", lambda: None):
                todos = P.cargar()
        self.assertNotIn("celestial_ellatte_verde_2", todos)
        self.assertIn("mi_heroe", todos)
        self.assertIn("celestial_ellatte_verde", todos)


if __name__ == "__main__":
    unittest.main()

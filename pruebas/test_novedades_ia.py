"""Talentos cada vez que se recargan, conocimiento por jefe, Sync Data y lo aprendido a la vista (2026-11-09)."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import entorno  # noqa: F401  (antes que lumen)

import cv2

from lumen import entrada, juego
from lumen.ia import conocimiento as K, lecciones as L
from lumen.modos import bestias_pisos1a3 as B
from lumen.modos import perros_piso4 as P4


class Talento(unittest.TestCase):
    def test_cooldown_y_limite_de_su_texto(self):
        self.assertEqual(P4.enfriamiento_talento({"odin"}), (3, None))
        self.assertEqual(P4.enfriamiento_talento({"nemesis_meliodas_oscuro"}), (3, 3))
        self.assertEqual(P4.enfriamiento_talento({"merlin_escanor_verde"}), (3, 1))

    def test_lo_vuelve_a_usar_al_recargarse(self):
        m = B.PajaroPisos1a3({"jugar": "Inteligente"})
        m._nueva_pelea()
        m.heroes_vistos = {"odin": 9}
        clics = []
        with mock.patch.object(entrada, "clic", lambda r, o, **k: clics.append(r)), \
                mock.patch.object(m, "capturar", lambda: (None, (0, 0))), \
                mock.patch.object(m, "_hay_talento", lambda p: True), \
                mock.patch.object(m, "_detectar_fase", lambda p, h: 1), \
                mock.patch.object(m, "_jugar_turno", lambda: None), \
                mock.patch.object(m, "esperar_corto", lambda s: None), \
                mock.patch.object(m, "log", lambda *a, **k: None), \
                mock.patch.object(juego, "mano_bloqueada", entorno.PlantillaFalsa("mano_bloqueada")):
            for _ in range(7):
                m._empezar_turno(set(), 4)
        self.assertEqual(clics.count(juego.COORD["talento"]), 3, "turnos 1, 4 y 7 (cooldown de 3)")


class Conocimiento(unittest.TestCase):
    def test_reglas_del_archivo(self):
        datos = {"x_f2": {"todas": {"preferir": "area"}, 2: {"evitar": ["ulti"]}}}
        es_area = lambda n: n.endswith("skill_2")  # noqa: E731
        valores, _ = K.aplicar({"a.skill_1": 1.0, "a.skill_2": 1.0, "a.ulti": 1.0}, "x_f2", 2, es_area, datos)
        self.assertEqual(valores, {"a.skill_1": 1.0, "a.skill_2": K.PREFERIR, "a.ulti": K.EVITAR})
        self.assertEqual(K.aplicar({"a.ulti": 1.0}, "x_f2", 1, es_area, datos)[0]["a.ulti"], 1.0, "otra fase")

    def test_lo_que_ensenaste_de_la_rata(self):
        self.assertEqual(K.reglas("rata_f2", 1).get("preferir"), "area")
        self.assertIn("ulti", K.reglas("rata_f3", 2).get("evitar"))


class SyncData(unittest.TestCase):
    def test_reconoce_la_pantalla(self):
        p = cv2.imread(str(Path(__file__).with_name("sync_data.png")))
        self.assertTrue(juego.sync_data.esta(p, 0.8))
        self.assertFalse(juego.sync_data.esta(cv2.imread(str(Path(__file__).with_name("pisos_nidhoggr.png"))), 0.8))


class Aprendido(unittest.TestCase):
    def test_texto_por_piso(self):
        carpeta = Path(tempfile.mkdtemp())
        L.aprender({"destino": "rata_f2", "resultado": "derrota", "fase_final": 1, "notas": [],
                    "turnos": [{"fase": 1, "turno": 1, "jugada": ["jugar", "a.skill_1"]}]}, carpeta=carpeta)
        self.assertEqual(L.claves_de("rata_pisos1a3", carpeta), ["rata_f2"])
        texto = L.texto_modo("rata_pisos1a3", carpeta)
        self.assertIn("Floor 2", texto)
        self.assertIn("evito", texto)
        self.assertIn("Todavía no", L.texto_modo("pajaro_pisos1a3", carpeta))


if __name__ == "__main__":
    unittest.main()

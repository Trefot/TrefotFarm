"""Paso 1: la pasiva de cada heroe cambia cuanto vale cada carta, y contra que jefe (2026-11-09)."""

import unittest

import entorno  # noqa: F401  (antes que lumen)

from lumen.ia import pasivas as PA


class Pasivas(unittest.TestCase):
    def test_leer_textos(self):
        p = PA.leer("This Unique ability only activates in Demonic Beast Battle Ratatoskr. Increases the hero's damage "
                    "dealt using single-target attacks by 200%.")
        self.assertEqual((p["jefe"], p["uno"], p["area"]), ("ratatoskr", 3.0, 1.0))
        self.assertTrue(PA.leer("In Demonic Beast Battle, allies gain...")["bestias"])
        self.assertEqual(PA.leer("Increases the hero's damage dealt by 30%.")["todas"], 1.3)

    def test_solo_contra_su_jefe(self):
        uno = lambda nombre: False  # noqa: E731  (todas de un objetivo)
        self.assertEqual(PA.factor("world_serpent_jormungand_rojo.skill_1", "rata_f2", uno), 3.0)
        self.assertEqual(PA.factor("world_serpent_jormungand_rojo.skill_1", "perros_f1", uno), 1.0)
        self.assertEqual(PA.factor("carta_sin_heroe", "rata_f2", uno), 1.0)

    def test_aplicar(self):
        valores, motivos = PA.aplicar({"world_serpent_jormungand_rojo.skill_1@2": 1.0, "x.skill_1": 1.0}, "rata_f1",
                                      lambda n: False)
        self.assertEqual(valores["world_serpent_jormungand_rojo.skill_1@2"], 3.0)
        self.assertIn("pasiva", motivos["world_serpent_jormungand_rojo.skill_1@2"][0])


if __name__ == "__main__":
    unittest.main()


class Reliquias(unittest.TestCase):
    """Todos los heroes llevan siempre su reliquia (el usuario, 2026-11-09): se aplica como la pasiva."""

    def test_reliquia_de_un_jefe(self):
        r = PA.leer("Increases the hero's damage dealt by 20% in Nidhoggr's Demonic Beast Battle.")
        self.assertEqual((r["jefe"], r["todas"]), ("nidhoggr", 1.2))
        self.assertTrue(PA.aplica(r, "serpiente_f3"))
        self.assertFalse(PA.aplica(r, "rata_f1"))

    def test_se_suma_a_la_pasiva(self):
        self.assertEqual(PA.factor("king_the_fairy_king_azul.skill_1", "rata_f1", lambda n: False), 1.8)

"""Menu Battle nuevo (actualizacion del juego, 2026-11-27): captura real con el nombre tapado."""
import unittest
from pathlib import Path

import cv2

from lumen import juego
from lumen.modos import fuerte_solgres as F, indura as I


class MenuBattle2026(unittest.TestCase):
    def setUp(self):
        self.p = cv2.imread(str(Path(__file__).with_name("menu_batalla_2026.png")))

    def test_reconoce_las_casillas(self):
        self.assertTrue(F.MAZMORRA_ORO.esta(self.p))
        self.assertTrue(F.ESPECIAL_FS.esta(self.p))
        self.assertTrue(I.BOSS_BATTLE.esta(self.p, 0.75))

    def test_las_casillas_estan_en_su_sitio(self):
        x, y, w, h = F.MAZMORRA_ORO.buscar(self.p)
        self.assertTrue(160 < x + w / 2 < 270 and 460 < y < 500, "Gold Dungeon")
        x, y, w, h = I.BOSS_BATTLE.buscar(self.p, 0.75)
        self.assertTrue(160 < x + w / 2 < 270 and 740 < y < 790, "Death Match")

    def test_no_se_confunden_con_otras_pantallas(self):
        otra = cv2.imread(str(Path(__file__).with_name("oro_lista_pisos.png")))
        self.assertFalse(F.MAZMORRA_ORO.esta(otra))
        self.assertFalse(I.BOSS_BATTLE.esta(otra, 0.75))


    def test_bestias_en_la_pestana_weekly(self):
        semanal = cv2.imread(str(Path(__file__).with_name("menu_weekly_2026.png")))
        self.assertTrue(juego.pestana_weekly.esta(self.p, 0.85), "en Daily: tocar Weekly")
        self.assertFalse(juego.pestana_weekly.esta(semanal, 0.85), "ya en Weekly: no tocarla")
        self.assertTrue(juego.nido_criaturas.esta(semanal))
        self.assertFalse(juego.nido_criaturas.esta(self.p))


if __name__ == "__main__":
    unittest.main()

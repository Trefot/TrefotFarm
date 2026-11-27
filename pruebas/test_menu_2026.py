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


    def test_ruleta_de_anuncios(self):
        ruleta = cv2.imread(str(Path(__file__).with_name("ad_bonus.png")))
        self.assertTrue(juego.anuncio_ruleta.esta(ruleta, 0.8))
        self.assertFalse(juego.anuncio_ruleta.esta(self.p, 0.8))
        self.assertFalse(juego.anuncio_ruleta.esta(cv2.imread(str(Path(__file__).with_name("resultado_tickets.png"))), 0.8))



class NivelesDemonio(unittest.TestCase):
    """Ventana nueva de Real-time Join Request: "No veo el nivel Normal de Red Demon" sin parar (2026-11-27)."""

    def _modo(self, lineas):
        from unittest import mock
        from lumen import entrada, ocr
        m = I.Indura.__new__(I.Indura)
        m.nombre, m.log = "Red Demon", lambda *a, **k: None
        self.clics, self.arrastres = [], []
        self.parches = [mock.patch.object(ocr, "disponible", lambda: True),
                        mock.patch.object(ocr, "lineas_con_posicion", lambda p, **k: lineas),
                        mock.patch.object(entrada, "clic", lambda pt, o, espera=0: self.clics.append(pt)),
                        mock.patch.object(entrada, "arrastrar", lambda a, b, o, *x, **k: self.arrastres.append((a, b)))]
        for pa in self.parches:
            pa.start()
            self.addCleanup(pa.stop)
        return m

    def test_toca_el_nivel_que_lee(self):
        m = self._modo([("Normal", (150, 626, 61, 13)), ("Hard", (358, 626, 41, 14))])
        self.assertTrue(m._nivel_por_texto(None, (0, 0), "Hard"))
        self.assertEqual(self.clics, [(378, 633)])

    def test_desliza_hacia_los_niveles_altos(self):
        m = self._modo([("Normal", (150, 626, 61, 13)), ("Hard", (358, 626, 41, 14))])
        self.assertFalse(m._nivel_por_texto(None, (0, 0), "Chaos"))
        self.assertEqual(self.arrastres, [I.DESLIZAR_NIVELES])

    def test_desliza_hacia_los_niveles_bajos(self):
        m = self._modo([("Hell", (150, 626, 40, 13)), ("Chaos", (358, 626, 50, 14))])
        self.assertFalse(m._nivel_por_texto(None, (0, 0), "Normal"))
        self.assertEqual(self.arrastres, [I.DESLIZAR_NIVELES[::-1]])

    def test_la_ocr_lee_la_captura_real(self):
        from lumen import ocr
        if not ocr.disponible():
            self.skipTest("sin OCR")
        p = cv2.imread(str(Path(__file__).with_name("niveles_demonio_2026.png")))
        textos = [t for t, (x, y, w, h) in ocr.lineas_con_posicion(p) if I.FRANJA_NIVELES[0] <= y + h // 2 <= I.FRANJA_NIVELES[1]]
        self.assertIn("Normal", textos)


if __name__ == "__main__":
    unittest.main()

"""Floor 4 del pajaro y del ciervo: guiones de AutoFarming traducidos a cartas con nombre (2026-11-10)."""

import unittest

import entorno  # noqa: F401  (antes que lumen)

from lumen import juego
from lumen.cartas import Carta, Rango, TipoCarta
from lumen.modos import MODOS
from lumen.modos import bestias_piso4 as B4

R = Rango
MELI, THOR, MEG, SHION = ("traitor_meliodas_oscuro", "thor_the_god_of_thunder_azul", "valkyrie_megellda_azul",
                          "shion_verde")
TYR, JORM, FREYR, HEL = ("god_of_war_tyr_verde", "world_serpent_jormungand_verde", "sun_god_freyr_rojo",
                         "repose_of_souls_hel_verde")


def mano(*cartas):
    """("heroe.carta", rango) o None (hueco vacio)."""
    salida = []
    for i, c in enumerate(cartas):
        if c is None:
            salida.append(Carta(i, (0, 0, 1, 1), None, TipoCarta.SUELO, R.NINGUNO, None))
            continue
        nombre, rango = c
        ulti = nombre.endswith(".ulti")
        salida.append(Carta(i, (0, 0, 1, 1), None, TipoCarta.ULTI if ulti else TipoCarta.NORMAL,
                            R.ULTI if ulti else rango, nombre))
    return salida


def estrategia(clase, ve=()):
    e = clase()
    e.ve = lambda plantilla, umbral=0.7: plantilla in ve
    e.por_defecto = lambda *a, **k: None
    return e


class Textos(unittest.TestCase):
    def test_lo_que_hace_cada_carta(self):
        c = mano((MEG + ".skill_2", R.BRONCE), (SHION + ".skill_1", R.BRONCE), (JORM + ".skill_2", R.BRONCE),
                 (THOR + ".ulti", R.ULTI))
        self.assertTrue(B4.es_curacion(c[0]), "Megellda azul cura")
        self.assertTrue(B4.contra_inmortalidad(c[1]), "Amplify de Shion")
        self.assertTrue(B4.quita_buffs(c[2]), "Jormungand verde quita buffs")
        self.assertTrue(B4.es_fuerte(c[3]))
        self.assertEqual(B4.color(c[1]), "verde")
        self.assertTrue(B4.es_hel(mano((HEL + ".skill_1", R.BRONCE))[0]))


class Pajaro(unittest.TestCase):
    def test_limpia_el_bloqueo_con_el_area_de_meliodas(self):
        e = estrategia(B4.EstrategiaPajaro4, ve=(juego.bloqueo_habilidades,))
        m = mano((THOR + ".skill_1", R.BRONCE), (MELI + ".skill_2", R.BRONCE), (SHION + ".skill_2", R.BRONCE))
        self.assertEqual(e.guion(1, 1, 0, m), 1)

    def test_fase1_guarda_las_de_plata(self):
        e = estrategia(B4.EstrategiaPajaro4)
        m = mano((THOR + ".skill_1", R.PLATA), (SHION + ".skill_1", R.PLATA), (MELI + ".skill_1", R.PLATA),
                 (SHION + ".skill_2", R.BRONCE))
        self.assertEqual(e.guion(1, 1, 2, m), 3, "juega la de bronce")

    def test_fase2_tres_de_plata_y_luego_con_todo(self):
        e = estrategia(B4.EstrategiaPajaro4)
        m = mano((THOR + ".skill_1", R.PLATA), (SHION + ".skill_1", R.PLATA), (MELI + ".skill_1", R.PLATA),
                 (SHION + ".skill_2", R.BRONCE))
        self.assertEqual(e.decidir(2, 1, 0, m)[0], 2, "una de plata")
        e.jugadas = [m[0], m[1]]
        m2 = mano(None, None, (MELI + ".skill_1", R.PLATA), (SHION + ".skill_2", R.BRONCE))
        self.assertEqual(e.guion(2, 1, 3, m2), 2)
        self.assertTrue(e.escudo, "3 de plata en el turno: el siguiente, con escudo")
        e.jugadas = []
        m3 = mano((SHION + ".skill_2", R.BRONCE), (THOR + ".ulti", R.ULTI), (MEG + ".skill_2", R.BRONCE))
        self.assertEqual(e.guion(2, 2, 0, m3), 1, "con escudo: la ulti")

    def test_fase3_quita_inmortalidades(self):
        e = estrategia(B4.EstrategiaPajaro4)
        e.pantalla = lambda: object()
        original = juego.inmortalidad.buscar_todas
        juego.inmortalidad.buscar_todas = lambda p, u=0.7: [1, 2]
        try:
            m = mano((THOR + ".skill_2", R.BRONCE), (SHION + ".skill_1", R.BRONCE), (MEG + ".skill_2", R.BRONCE))
            self.assertEqual(e.guion(3, 1, 0, m), 1, "Amplify mientras tenga inmortalidad")
        finally:
            juego.inmortalidad.buscar_todas = original

    def test_fase4_evasion_con_la_ulti_de_meliodas(self):
        e = estrategia(B4.EstrategiaPajaro4, ve=(juego.evasion,))
        m = mano((THOR + ".ulti", R.ULTI), (MELI + ".ulti", R.ULTI), (SHION + ".skill_2", R.BRONCE))
        self.assertEqual(e.guion(4, 1, 0, m), 1)

    def test_fase4_sin_evasion_no_gasta_la_ulti_de_meliodas(self):
        e = estrategia(B4.EstrategiaPajaro4)
        m = mano((MELI + ".ulti", R.ULTI), (SHION + ".skill_2", R.BRONCE))
        self.assertEqual(e.guion(4, 1, 0, m), 1)


class Ciervo(unittest.TestCase):
    def test_apertura_de_la_fase_1(self):
        e = estrategia(B4.EstrategiaCiervo4)
        m = mano((TYR + ".skill_1", R.PLATA), (TYR + ".skill_2", R.BRONCE), (JORM + ".skill_1", R.BRONCE),
                 (THOR + ".skill_1", R.PLATA), (THOR + ".skill_2", R.BRONCE), (FREYR + ".skill_1", R.BRONCE))
        self.assertEqual([e.guion(1, 1, a, m) for a in range(4)], [1, 2, 4, 0],
                         "Tyr baja, Jormungand, Thor bajo, Tyr alta")

    def test_ruleta_de_colores_de_la_fase_4(self):
        e = estrategia(B4.EstrategiaCiervo4)
        m = mano((THOR + ".skill_1", R.BRONCE), (JORM + ".skill_1", R.BRONCE), (FREYR + ".skill_2", R.BRONCE))
        e.jugadas = mano((FREYR + ".skill_1", R.BRONCE))
        self.assertEqual(e.guion(4, 4, 1, m), 1, "despues de roja, verde")
        e.jugadas = mano((JORM + ".skill_2", R.BRONCE))
        self.assertEqual(e.guion(4, 4, 1, m), 0, "despues de verde, azul")

    def test_fase3_guarda_la_ulti_de_freyr(self):
        e = estrategia(B4.EstrategiaCiervo4)
        m = mano((FREYR + ".ulti", R.ULTI), (FREYR + ".skill_1", R.BRONCE), (FREYR + ".skill_2", R.BRONCE))
        e.color_turno = "rojo"
        self.assertNotEqual(e.guion(3, 2, 3, m), 0)


class Modos(unittest.TestCase):
    def test_activos_con_su_bestia(self):
        for clave, bestia in (("pajaro_piso4", juego.pajaro), ("ciervo_piso4", juego.ciervo)):
            m = MODOS[clave]({"victorias": 0, "extra": 0, "pociones": True, "max_pociones": 0})
            self.assertIs(m.bestia, bestia)
            self.assertIs(m.estrategia.modo, m)
            self.assertIsNone(m.equipo, "juega con el equipo puesto")

    def test_cuatro_fases(self):
        m = MODOS["pajaro_piso4"]({"victorias": 0, "extra": 0, "pociones": True, "max_pociones": 0})
        guardado = {n: getattr(juego, n) for n in ("fase_1", "fase_2", "fase_3", "fase_4")}
        try:
            for n in guardado:
                setattr(juego, n, entorno.PlantillaFalsa(n))
            self.assertEqual(m._detectar_fase({"fase_4"}, 4), 4)
            self.assertEqual(m._detectar_fase({"fase_1"}, 4), 1)
        finally:
            for n, v in guardado.items():
                setattr(juego, n, v)


if __name__ == "__main__":
    unittest.main()


class Navegacion(unittest.TestCase):
    """2026-11-10: el plan del dia fallaba (error al ganar o perder) y el pajaro se quedaba quieto en los pisos
    de los perros."""

    def setUp(self):
        self.guardado = {n: getattr(juego, n) for n in ("carga_bestias", "piso3_superado", "piso3_superado_pajaro",
                                                        "piso3_superado_ciervo", "cancelar")}
        for n in self.guardado:
            setattr(juego, n, entorno.PlantillaFalsa(n))
        self.atras = B4.ATRAS
        B4.ATRAS = entorno.PlantillaFalsa("atras")

    def tearDown(self):
        for n, v in self.guardado.items():
            setattr(juego, n, v)
        B4.ATRAS = self.atras

    def modo(self, clave):
        m = MODOS[clave]({"victorias": 0, "extra": 0, "pociones": True, "max_pociones": 0})
        if clave != "perros_piso4":  # su imagen de "Floor 3 Cleared", la falsa de la prueba
            m.piso3_superado = getattr(juego, "piso3_superado_" + clave.split("_")[0])
        return m

    def test_al_ganar_o_perder_no_se_rompe(self):
        for clave in ("perros_piso4", "pajaro_piso4"):
            m = self.modo(clave)
            self.assertTrue(m._volvio_a_pisos({"carga_bestias"}))
            self.assertFalse(m._volvio_a_pisos(set()))

    def test_sale_de_los_pisos_de_otra_bestia(self):
        m = self.modo("pajaro_piso4")
        clics = []
        m.clic_si = lambda plantilla, p, o, **k: clics.append(plantilla) or plantilla is B4.ATRAS
        m.log = lambda *a, **k: None
        m._bestia_de_los_pisos = None
        original = B4.B13.BestiaPisos1a3._bestia_de_los_pisos
        B4.B13.BestiaPisos1a3._bestia_de_los_pisos = lambda self, p: 2  # la cabecera dice Skoll and Hati
        try:
            self.assertIsNone(m.ir_a_perros({"atras", "piso3_superado"}, (0, 0)))
        finally:
            B4.B13.BestiaPisos1a3._bestia_de_los_pisos = original
        self.assertIn(B4.ATRAS, clics, "vuelve atras")

    def test_en_sus_pisos_elige_el_piso(self):
        m = self.modo("pajaro_piso4")
        m.log = lambda *a, **k: None
        m.clic_si = lambda *a, **k: False
        self.assertEqual(m.ir_a_perros({"piso3_superado_pajaro"}, (0, 0)), "elegir_piso")

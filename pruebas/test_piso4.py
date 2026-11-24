"""Floor 4 del pajaro y del ciervo: lo que pide cada fase (7dshub) y las reglas del usuario."""

import unittest
from unittest import mock

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
    def test_el_bloqueo_se_quita_curando(self):
        """7dshub: el bloqueo no afecta a posturas ni curaciones. El area de Meliodas solo limpia con su reliquia."""
        e = estrategia(B4.EstrategiaPajaro4, ve=(juego.bloqueo_habilidades,))
        m = mano((THOR + ".skill_1", R.BRONCE), (MELI + ".skill_2", R.BRONCE), (MEG + ".skill_2", R.BRONCE))
        self.assertEqual(e.guion(1, 1, 0, m), 2, "la curacion de Megellda")
        e.jugadas = [m[2]]
        self.assertNotEqual(e.guion(1, 1, 1, m[:2]), None, "curado ya: sigue con el turno")

    def test_fase3_guarda_la_ulti_que_quita_buffs_para_la_evasion(self):
        e = estrategia(B4.EstrategiaPajaro4)
        e.pantalla = lambda: None  # sin inmortalidades a la vista
        m = mano((MELI + ".ulti", R.ULTI), (THOR + ".skill_1", R.BRONCE))
        self.assertEqual(e.guion(3, 1, 0, m), 1)

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
        self.assertTrue(e.proteccion, "3 de plata en el turno: el siguiente, con escudo")
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

    def test_fase3_casi_muerto_con_inmortalidades_no_gasta_ultis(self):
        """2026-11-24: al 10 % y con inmortalidades gastaba las ultis de Gawain y Thor; sin cartas que las quiten,
        mueve para que salgan."""
        from types import SimpleNamespace

        from lumen.vida_jefe import Vida

        e = estrategia(B4.EstrategiaPajaro4)
        e.modo = SimpleNamespace(vida_jefe=Vida("morado", 0.10), log=lambda *a, **k: None)
        e.ve = lambda *a, **k: False
        e.pantalla = lambda: "pantalla"
        m = mano(("gawain.ulti", R.ULTI), ("thor_the_god_of_thunder_azul.ulti", R.ULTI),
                 ("god_of_war_tyr_verde.skill_2", R.BRONCE), ("odin.single", R.BRONCE))
        with mock.patch.object(B4.juego.inmortalidad, "buscar_todas", lambda p, u: [1, 2, 3]):
            self.assertIsInstance(e.guion(3, 2, 0, m), tuple, "mueve, no la ulti")
            thor = mano(("gawain.ulti", R.ULTI), ("thor_the_god_of_thunder_azul.skill_2", R.BRONCE))
            self.assertEqual(e.guion(3, 2, 0, thor), 1, "Thunderbolt de Thor tambien las quita (el usuario)")
            amplify = mano(("god_of_war_tyr_verde.skill_1", R.PLATA), ("gawain.ulti", R.ULTI))
            self.assertEqual(e.guion(3, 2, 0, amplify), 0, "la de Tyr (Amplify) quita una inmortalidad")
        e.modo = SimpleNamespace(vida_jefe=Vida("morado", 0.60), log=lambda *a, **k: None)
        with mock.patch.object(B4.juego.inmortalidad, "buscar_todas", lambda p, u: [1, 2, 3]):
            self.assertNotIsInstance(e.guion(3, 2, 0, m), tuple, "al 60 % aun se le pega")

    def test_fase4_evasion_con_la_ulti_de_meliodas(self):
        e = estrategia(B4.EstrategiaPajaro4, ve=(juego.evasion,))
        m = mano((THOR + ".ulti", R.ULTI), (MELI + ".ulti", R.ULTI), (SHION + ".skill_2", R.BRONCE))
        self.assertEqual(e.guion(4, 1, 0, m), 1)

    def test_fase4_sin_evasion_no_gasta_la_ulti_de_meliodas(self):
        e = estrategia(B4.EstrategiaPajaro4)
        m = mano((MELI + ".ulti", R.ULTI), (SHION + ".skill_2", R.BRONCE))
        self.assertEqual(e.guion(4, 1, 0, m), 1)


class Ciervo(unittest.TestCase):
    def test_fase_1_ulti_primero_y_la_cuarta_carga_ultis(self):
        """7dshub: el Torrente se quita usando la ulti; la 4.a accion mueve una carta para cargar otra."""
        e = estrategia(B4.EstrategiaCiervo4)
        m = mano((TYR + ".skill_1", R.PLATA), (TYR + ".skill_2", R.BRONCE), (THOR + ".ulti", R.ULTI),
                 (THOR + ".skill_1", R.PLATA), (FREYR + ".skill_1", R.BRONCE))
        self.assertEqual(e.guion(1, 1, 0, m), 2, "la ulti de Thor")
        self.assertIsInstance(e.guion(1, 1, 3, m), tuple, "la 4.a accion mueve")

    def test_ruleta_de_colores_de_la_fase_4(self):
        e = estrategia(B4.EstrategiaCiervo4)
        m = mano((THOR + ".skill_1", R.BRONCE), (JORM + ".skill_1", R.BRONCE), (FREYR + ".skill_2", R.BRONCE))
        e.jugadas = mano((FREYR + ".skill_1", R.BRONCE))
        self.assertEqual(e.guion(4, 2, 1, m), 1, "despues de roja, verde")
        e.jugadas = mano((JORM + ".skill_2", R.BRONCE))
        self.assertEqual(e.guion(4, 2, 1, m), 0, "despues de verde, azul")

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

    def test_si_tambien_se_ve_la_imagen_de_otra_bestia_no_cree_que_son_sus_pisos(self):
        """2026-11-24: pidio el pajaro con el juego en los pisos del ciervo y peleo el ciervo con el guion del
        pajaro."""
        m = self.modo("pajaro_piso4")
        self.assertFalse(m._es_mi_piso4({"piso3_superado_pajaro", "piso3_superado_ciervo"}))
        self.assertTrue(m._es_mi_piso4({"piso3_superado_pajaro"}))

    def test_en_sus_pisos_elige_el_piso(self):
        m = self.modo("pajaro_piso4")
        m.log = lambda *a, **k: None
        m.clic_si = lambda *a, **k: False
        self.assertEqual(m.ir_a_perros({"piso3_superado_pajaro"}, (0, 0)), "elegir_piso")


class Derrota(unittest.TestCase):
    def test_se_ve_en_el_registro_y_dice_por_que(self):
        m = MODOS["pajaro_piso4"]({"victorias": 0, "extra": 0, "pociones": True, "max_pociones": 0})
        m.derrotas, m.fase, m.turno_fase, m.turnos_sin_jugar = 2, 2, 9, 6
        texto = m.texto_derrota()
        self.assertIn("DERROTA #2 en la fase 2, turno 9", texto)
        self.assertIn("6 turnos seguidos sin poder jugar", texto)


class ReinicioPorBloqueo(unittest.TestCase):
    """El usuario, 2026-11-13: con todas las cartas bloqueadas en la fase 2 del pajaro, reiniciar ya."""

    def modo(self, clave):
        m = MODOS[clave]({"victorias": 0, "extra": 0, "pociones": True, "max_pociones": 0})
        m.log = lambda *a, **k: None
        return m

    def leer(self, bloqueadas, libres=0):
        cartas = mano(*([(SHION + ".skill_1", R.BRONCE)] * (bloqueadas + libres)))
        for c in cartas[:bloqueadas]:
            c.tipo = TipoCarta.BLOQUEADA
        return cartas

    def test_pajaro_fase2_todo_bloqueado_reinicia(self):
        m = self.modo("pajaro_piso4")
        m.fase = 2
        B4.C.leer_mano, original = (lambda p: self.leer(8)), B4.C.leer_mano
        try:
            self.assertTrue(m._reiniciar_por_bloqueo(object()))
            B4.C.leer_mano = lambda p: self.leer(7, libres=1)
            self.assertFalse(m._reiniciar_por_bloqueo(object()), "con una carta jugable se sigue")
            m.fase = 3
            B4.C.leer_mano = lambda p: self.leer(8)
            self.assertFalse(m._reiniciar_por_bloqueo(object()), "solo en la fase 2")
        finally:
            B4.C.leer_mano = original

    def test_el_ciervo_no(self):
        m = self.modo("ciervo_piso4")
        m.fase = 2
        self.assertFalse(m._reiniciar_por_bloqueo(object()))

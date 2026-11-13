"""Efectos por rango y contramedidas por funcion, sin personajes obligatorios."""

import unittest
from types import SimpleNamespace
import entorno  # noqa: F401
from lumen.cartas import Carta, Rango, TipoCarta
from lumen.ia import decidir, resolver
from lumen.modos.bestias_piso4 import EstrategiaPajaro4


DANO = "Inflicts damage equal to 180% of Attack on one enemy."
FICHAS = {
    "alternativo": {
        "skill_1": {
            "rangos": [
                DANO,
                DANO,
                "Removes Buffs from one enemy and inflicts damage equal to 300% of Attack.",
            ]
        }
    },
    "tardio": {"skill_1": {"rangos": [DANO + " Removes Buffs from one enemy."] * 3}},
    "limpiador": {
        "skill_1": {
            "rangos": [
                DANO,
                "Removes Debuffs from all allies.",
                "Removes Debuffs from all allies.",
            ]
        }
    },
    "golpeador": {"skill_1": {"rangos": [DANO + " Cannot be evaded."] * 3}},
}


def carta(pid, rango=Rango.BRONCE):
    return Carta(nombre=pid + ".skill_1", rango=rango, tipo=TipoCarta.NORMAL)


def lector():
    return decidir.LectorCartas(biblioteca={}, textos={}, fichas=FICHAS)


class ResolverMecanicas(unittest.TestCase):
    def test_no_atribuye_el_efecto_del_oro_al_bronce(self):
        l = lector()
        self.assertFalse(
            resolver.satisface(l.efectos_carta(carta("alternativo")), "evasion")
        )
        self.assertTrue(
            resolver.satisface(
                l.efectos_carta(carta("alternativo", Rango.ORO)), "evasion"
            )
        )
        self.assertEqual(
            l.efectos_carta(
                Carta(
                    nombre="sin_ficha.skill_1", tipo=TipoCarta.NORMAL, rango=Rango.ORO
                )
            ),
            [],
        )

    def test_no_quita_evasion_despues_de_que_el_golpe_haya_fallado(self):
        self.assertFalse(
            resolver.satisface(lector().efectos_carta(carta("tardio")), "evasion")
        )

    def test_condicion_no_observada_no_se_da_por_cumplida(self):
        l = decidir.LectorCartas(
            biblioteca={},
            textos={},
            fichas={
                "condicional": {
                    "skill_1": {
                        "rangos": [
                            "Removes Buffs from one enemy if the hero has 3 Buffs. "
                            + DANO
                        ]
                        * 3
                    }
                }
            },
        )
        self.assertEqual(l.efectos_carta(carta("condicional")), [])

    def test_otro_personaje_resuelve_evasion_por_su_efecto(self):
        e = EstrategiaPajaro4()
        e.jugador._lector = lector()
        e.jugador.observacion = {"senales": {"evasion": {"confianza": 0.95}}}
        m = [carta("tardio"), carta("alternativo", Rango.ORO), carta("golpeador")]
        self.assertEqual(
            e.decidir(4, 1, 0, m)[0], 2, "la normal de menor rango que sirve"
        )
        self.assertIn("Mecánica observada", e.jugador.razones[m[2].nombre][0])

    def test_sin_senal_no_se_inventa_que_el_jefe_tenga_evasion(self):
        for destino, fase, obs in (
            ("pajaro_piso4", 4, {}),
            ("pajaro_piso4", 4, {"senales": {"evasion": {"confianza": 0.7}}}),
            ("ciervo_piso4", 4, {"senales": {"evasion": {"confianza": 0.99}}}),
        ):
            self.assertIsNone(
                resolver.por_estado(destino, fase, [carta("golpeador")], obs, lector())
            )

    def test_limpia_bloqueo_con_una_carta_de_otro_heroe_si_su_rango_lo_permite(self):
        l = lector()
        obs = {"senales": {"bloqueo": {"confianza": 0.99}}}
        self.assertIsNone(
            resolver.por_estado("pajaro_piso4", 1, [carta("limpiador")], obs, l)
        )
        e = resolver.por_estado(
            "pajaro_piso4", 1, [carta("limpiador", Rango.PLATA)], obs, l
        )
        self.assertEqual(e.indice, 0)

    def test_mismo_rango_del_jefe_permite_tres_cartas_de_oro(self):
        requisito = resolver.requisito_rango("pajaro_piso4", 2)
        self.assertEqual(requisito, (3, 2))
        m = [carta("a", Rango.ORO), carta("b", Rango.ORO), carta("c", Rango.ORO)]
        e = EstrategiaPajaro4()
        self.assertIn(e.guion(2, 1, 0, m), range(3))
        self.assertEqual(resolver.grupo_de_rango(m, [], 4, requisito)[0], Rango.ORO)
        self.assertIsNone(resolver.grupo_de_rango(m[:2], [], 2, requisito))

    def test_pajaro_activa_proteccion_al_cerrar_turno_con_tres_del_mismo_rango(self):
        e = EstrategiaPajaro4()
        e.jugadas = [carta("a", Rango.ORO), carta("b", Rango.ORO), carta("c", Rango.ORO), carta("d")]
        e.turno_completado(2, 1)
        self.assertTrue(e.escudo)
        e.jugadas = [carta("a", Rango.PLATA), carta("b", Rango.ORO), carta("c", Rango.ORO)]
        e.turno_completado(2, 2)
        self.assertFalse(e.escudo, "tres de rangos mezclados no cumplen mismo rango")

    def test_no_presupone_reliquia_equipada_para_limpiar(self):
        l = decidir.LectorCartas(textos={})
        meli = Carta(
            nombre="traitor_meliodas_oscuro.skill_2",
            rango=Rango.BRONCE,
            tipo=TipoCarta.NORMAL,
        )
        self.assertFalse(resolver.satisface(l.efectos_carta(meli), "limpiar"))

    def test_informe_de_equipo_avisa_rangos_y_limites(self):
        l = lector()
        l.biblioteca = {"alternativo": SimpleNamespace(cartas={"skill_1": None})}
        texto = resolver.informe_equipo(
            "pajaro_piso4", ["alternativo", "inexistente"], l
        )
        self.assertIn("Sin ficha: inexistente", texto)
        self.assertIn("No simula una victoria", texto)
        self.assertIn("oro", texto)
        self.assertIn("3:2", texto)

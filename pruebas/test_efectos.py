"""Lector de efectos (IA.md, pieza 1): textos reales del juego -> efectos y mecanicas.

Cada texto nuevo que el lector deba entender se anade aqui, copiado tal cual del juego (cliente en ingles).
"""

import unittest

import entorno  # noqa: F401  (antes que lumen)

from lumen.ia.efectos import Efecto, Mecanica, cobertura, efectos, jefe, mecanicas, no_entendido

# Skill Info de [Master of Light] Sun God Freyr (captura del usuario, 2026-10-29)
RAINING_BLADES = ("Inflicts Cleave damage, which does not activate Crit Damage, equal to 220% of Attack on one "
                  "enemy, then decreases their Attack-related stats by 20% for 1 turn(s).")

# Enemy Info de Transcendent Eikthyrnir, Floor 4 (capturas del usuario, 2026-10-29)
CIERVO_F1 = ('The Demonic Beast uses "Splash Shower" every set number of turns to apply Torrent on enemies. All '
             'Torrent effects are removed when the enemy uses an Ultimate Move or when they are hit by the Demonic '
             'Beast\'s "Icy Pond".')
CIERVO_F2 = ("At the start of the battle, the Demonic Beast gains Damage Taken Decrease effects for Strength, HP, "
             "and Speed attributes. When you continuously attack the Demonic Beast with the same attribute, the "
             "Damage Taken Decrease effect related to the attribute that is weak against the attacker's attribute "
             "will be removed.")
CIERVO_F3 = ("When the Demonic Beast is attacked a certain number of times using the same attribute all enemies "
             "gain Eikthyrnir's Protection. Enemies with Eikthyrnir's Protection do not take damage from the "
             'Demonic Beast\'s "Fierce Rush" skill.')
CIERVO_F4 = ("At the start of the battle, the Demonic Beast gains Immortality and Attribute Defense against all "
             "attributes. 1 Immortality effect is removed when it is attacked a certain number of times in a "
             "certain sequence of attributes. The Attribute Defense of each attribute is removed at certain "
             "amounts of HP.")
CIERVO_PASIVA_F1 = "Recovers HP equal to 50% of the damage dealt to enemies with Torrent."
CIERVO_PASIVA_F3 = "Increases the hero's Crit Chance by 10% for every orb filled in the hero's Ultimate Move Gauge."


class Heroes(unittest.TestCase):
    def test_raining_blades(self):
        self.assertEqual(efectos(RAINING_BLADES), [
            Efecto("dano", 220.0, "uno", None, "cleave"),
            Efecto("debuff", 20.0, "uno", 1, "attack"),
        ])
        self.assertEqual(no_entendido(RAINING_BLADES), [])

    def test_formas_habituales(self):
        # Frases con la forma tipica del juego (cambiar por las reales cuando lleguen de la captura de heroes).
        casos = {
            "Deals damage equal to 200% of Attack to all enemies.": [Efecto("dano", 200.0, "todos")],
            "Inflicts damage equal to 150% of their Attack on one enemy, then 100% of Attack again":
                [Efecto("dano", 150.0, "uno"), Efecto("dano", 100.0, "uno")],
            "Removes the target's Stance before inflicting damage equal to 180% of Attack on one enemy.":
                [Efecto("dano", 180.0, "uno"), Efecto("quitar_postura", None, "uno")],
            "Increases all allies' Attack by 30% for 2 turn(s).": [Efecto("buff", 30.0, "aliados", 2, "attack")],
            "Removes all debuffs from all allies and restores HP equal to 20% of max HP.":
                [Efecto("limpiar", None, "aliados"), Efecto("curar", 20.0, "aliados")],
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(efectos(texto), esperado)

    def test_cobertura_y_pendientes(self):
        inf = cobertura([RAINING_BLADES, "Taunts all enemies for 2 turn(s)."])
        self.assertEqual((inf.entendidas, inf.total), (2, 3))
        self.assertEqual(inf.pendientes, ["Taunts all enemies for 2 turn(s)"])


class Jefes(unittest.TestCase):
    def test_fases_del_ciervo_floor4(self):
        self.assertEqual(mecanicas(CIERVO_F1), [Mecanica("torrent", ("ulti",))])
        self.assertEqual(mecanicas(CIERVO_F2), [Mecanica("reduccion_dano_atributo", ("mismo_atributo",))])
        self.assertEqual(mecanicas(CIERVO_F3), [Mecanica("proteccion", ("mismo_atributo",), "Eikthyrnir")])
        self.assertEqual([m.tipo for m in mecanicas(CIERVO_F4)], ["inmortalidad", "defensa_atributo"])
        self.assertEqual(mecanicas(CIERVO_F4)[0].contra, ("secuencia_atributos",))
        self.assertEqual(mecanicas(CIERVO_PASIVA_F3), [Mecanica("bonus_por_orbes", ("cargar_ulti",), "critico (chance)")])

    def test_el_jefe_entero_une_la_curacion_con_el_torrent(self):
        sola = mecanicas(CIERVO_PASIVA_F1)[0]
        self.assertEqual((sola.tipo, sola.depende), ("curacion_jefe", "torrent"))
        todas = {m.tipo: m for m in jefe([CIERVO_F1, CIERVO_PASIVA_F1, CIERVO_F2, CIERVO_F3, CIERVO_F4])}
        self.assertEqual(todas["curacion_jefe"].contra, ("ulti",), "quitar el Torrent = usar la ulti")
        self.assertEqual(set(todas), {"torrent", "curacion_jefe", "reduccion_dano_atributo", "proteccion",
                                      "inmortalidad", "defensa_atributo"})


if __name__ == "__main__":
    unittest.main()

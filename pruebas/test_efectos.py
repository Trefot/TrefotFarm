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
        inf = cobertura([RAINING_BLADES, "Sings a lullaby to the moon.", "Lv", "3/5 2", "(Can be stacked up to 3 times)"])
        self.assertEqual((inf.entendidas, inf.total), (2, 3), "los restos del lector de texto y las notas no cuentan")
        self.assertEqual(inf.pendientes, ["Sings a lullaby to the moon"])

    def test_cartas_reales(self):
        # Textos tal cual de la captura de heroes (2026-10-27), con los fallos del lector de texto incluidos.
        casos = {
            # Captain Meliodas, Moonlight Divide
            "Cancels Buffs and Stances on one enemy, inflicts damage equal to 490% of Attack, then Stuns for turn(s). "
            "*Stun: Prohibits all actions. LV. 1/6 4": {"dano", "quitar_postura", "quitar_buffs", "aturdir"},
            # Guardian Guila, Shot Bombs
            "Inflicts damage equal to 180% of Attack on one enemy. Ignites for 3 turn(s). *Ignite: Damage taken by "
            "target(s) +10% (Can be stacked).": {"dano", "dano_tiempo"},
            # Fraudrin of Selflessness, Shadow Barrage (texto desordenado: el % quedo al final)
            "Inflicts damage equal to of Attack on one enemy 945% and depletes 3 Ultimate Move Gauge orb(s).":
                {"dano", "quitar_orbes"},
            # Covenant of Light Sariel, Slashing Wind
            "Assumes a Stance for I turn(s) which Taunts enemies and inflicts damage equal to 240% of Attack when "
            "taking damage. *Taunt: Directs all attacks to self.": {"postura", "provocar", "dano"},
            # Monspeet of Reticence, Scarlet Blaze Shot
            "Inflicts Weak Point damage equal to 90% of Attack on all enemies. *Weak Point: 3x damage against "
            "Debuffed enemies.": {"dano", "dano_extra"},
        }
        for texto, tipos in casos.items():
            with self.subTest(texto=texto[:40]):
                self.assertEqual({e.tipo for e in efectos(texto)}, tipos)
        guila = efectos("Inflicts damage equal to 180% of Attack on one enemy. Ignites for 3 turn(s).")
        self.assertEqual((guila[0].valor, guila[0].objetivo, guila[1].turnos, guila[1].detalle), (180.0, "uno", 3, "ignite"))
        fraudrin = efectos("Inflicts damage equal to of Attack on one enemy 945% and depletes 3 Ultimate Move Gauge orb(s).")
        self.assertEqual(fraudrin[0].valor, 945.0)
        self.assertEqual(efectos("Assumes a Stance for I turn(s)")[0].turnos, 1, "el lector de texto lee 1 como I")
        drole = efectos("damage equal to 160% of Attack on one Inflicts Detonate enemy.")
        self.assertEqual((drole[0].tipo, drole[0].valor, drole[0].objetivo), ("dano", 160.0, "uno"))


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


class Pasivas(unittest.TestCase):
    def test_pasivas_y_reliquias_reales(self):
        # Textos de la captura de pasivas (2026-10-29), tal cual.
        casos = {
            "Increases allies' HP-related stats by 15%.": {"buff"},  # reliquia de Princess Elizabeth
            "The hero's damage taken from skills during the enemy's turn does not exceed 40% of Max HP.": {"tope_dano"},
            "Fills the heros utimate Move Gauge by 1 orb(s) phen an ally dies.": {"orbes"},
            "Applicable allies damage taken -20%.": {"reduccion_dano"},
            "The hero is given the additional race Demon.": {"raza_extra", "aplica_estado"},
            "Grants Human allies I Evade for I turn at the start of the allies' turn.": {"evasion"},
        }
        for texto, tipos in casos.items():
            with self.subTest(texto=texto[:40]):
                self.assertEqual({e.tipo for e in efectos(texto)}, tipos)

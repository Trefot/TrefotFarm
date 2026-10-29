"""Decidir (IA.md, pieza 4): el valor de cada carta segun lo que pide el jefe en la fase."""

import unittest
from unittest import mock

import entorno  # noqa: F401  (antes que lumen)

from lumen import inteligencia as I
from lumen.cartas import Carta, Rango, TipoCarta as T
from lumen.ia import decidir as D
from lumen.ia.efectos import Efecto, Mecanica
from test_efectos import RAINING_BLADES

POSTURA = [Mecanica("postura", ("quitar_postura",))]
EFECTOS = {  # lo que hace cada carta de prueba
    "a.quita": [Efecto("quitar_postura", None, "uno"), Efecto("dano", 150.0, "uno")],
    "a.golpe": [Efecto("dano", 200.0, "uno")],
    "a.doble": [Efecto("dano", 100.0, "uno"), Efecto("dano", 100.0, "uno")],
    "a.limpia": [Efecto("limpiar", None, "aliados")],
    "a.esquiva": [Efecto("ignora_evasion"), Efecto("dano", 120.0, "uno")],
    "a.ulti": [Efecto("dano", 400.0, "todos")],
}
COLORES = {"a": "rojo", "b": "verde"}


def ajustar(mecanicas, valores=None, color_turno=None):
    valores = valores or {n: 1.0 for n in EFECTOS}
    return D.ajustar(valores, mecanicas, lambda n: EFECTOS.get(D.base(n), []),
                     lambda n: COLORES.get(n.split(".")[0]), color_turno)


class Jefes(unittest.TestCase):
    def test_mecanicas_del_ciervo_por_fase(self):
        f1 = {m.tipo: m for m in D.mecanicas_de("ciervo_piso4", 1)}
        self.assertEqual(set(f1), {"torrent", "curacion_jefe"})
        self.assertEqual(f1["curacion_jefe"].contra, ("ulti",))
        self.assertEqual({m.tipo for m in D.mecanicas_de("ciervo_piso4", 3)}, {"proteccion", "bonus_por_orbes"})
        self.assertEqual({m.tipo for m in D.mecanicas_de("ciervo_piso4", 4)}, {"inmortalidad", "defensa_atributo"})
        self.assertEqual(D.mecanicas_de("ciervo_piso4", 9), [])
        self.assertEqual(D.mecanicas_de("no_existe", 1), [])


class Ajustes(unittest.TestCase):
    def test_sin_mecanicas_no_cambia_nada(self):
        nuevos, razones = ajustar([])
        self.assertTrue(all(v == 1.0 for v in nuevos.values()))
        self.assertEqual(razones, {})

    def test_postura(self):
        nuevos, razones = ajustar(POSTURA)
        self.assertEqual(nuevos["a.quita"], 3.0)
        self.assertEqual(nuevos["a.golpe"], 1.0)
        self.assertEqual(razones["a.quita"], ["quita la postura"])

    def test_ulti_contra_el_torrent_del_ciervo(self):
        nuevos, _ = ajustar(D.mecanicas_de("ciervo_piso4", 1), {"a.ulti": 1.0, "a.ulti@2": 1.0, "a.golpe": 1.0})
        self.assertEqual((nuevos["a.ulti"], nuevos["a.ulti@2"], nuevos["a.golpe"]), (2.0, 2.0, 1.0))

    def test_evasion(self):
        nuevos, _ = ajustar([Mecanica("evasion", ("ignora_evasion", "ulti"))])
        self.assertEqual((nuevos["a.esquiva"], nuevos["a.ulti"], nuevos["a.golpe"], nuevos["a.limpia"]),
                         (3.0, 1.5, 0.6, 1.0))

    def test_mismo_atributo(self):
        valores = {"a.golpe": 1.0, "b.golpe": 1.0}
        nuevos, razones = ajustar(D.mecanicas_de("ciervo_piso4", 2), valores, color_turno="rojo")
        self.assertEqual((nuevos["a.golpe"], nuevos["b.golpe"]), (1.5, 0.7))
        self.assertEqual(razones["b.golpe"], ["rompe el rojo"])
        self.assertEqual(ajustar(D.mecanicas_de("ciervo_piso4", 2), valores)[0], valores, "sin color aun: igual")

    def test_bloqueo_golpes_y_orbes(self):
        nuevos, _ = ajustar([Mecanica("bloqueo", ("limpiar",)), Mecanica("inmortalidad", ("golpes",)),
                             Mecanica("bonus_por_orbes", ("cargar_ulti",))])
        self.assertEqual((nuevos["a.limpia"], nuevos["a.doble"], nuevos["a.ulti"]), (3.0, 1.5, 0.6))


class Lector(unittest.TestCase):
    def test_efectos_y_color_de_una_carta_real(self):
        lector = D.LectorCartas(textos={"raining blades": RAINING_BLADES})
        self.assertEqual([e.tipo for e in lector.efectos_de("sun_god_freyr_rojo.skill_2@1")], ["dano", "debuff"])
        self.assertEqual(lector.color_de("sun_god_freyr_rojo.skill_2"), "rojo")
        self.assertEqual(lector.efectos_de("sun_god_freyr_rojo.skill_1"), [], "sin texto capturado: nada")


class EnElJugador(unittest.TestCase):
    def test_con_postura_elige_la_carta_que_la_quita(self):
        mano = [Carta(0, tipo=T.NORMAL, rango=Rango.BRONCE, nombre="a.quita"),
                Carta(1, tipo=T.NORMAL, rango=Rango.BRONCE, nombre="a.golpe")]
        j = I.Jugador()
        j._indice = object()
        j._tasador = mock.Mock(valores=lambda nombres: {"a.quita": 1.0, "a.golpe": 1.2})
        j._lector = mock.Mock(efectos_de=lambda n: EFECTOS.get(D.base(n), []), color_de=lambda n: "rojo")
        with mock.patch.object(I, "agrupar_por_dibujo", lambda mano, identificar: None):
            self.assertEqual(j.elegir(mano, 1), ("jugar", 1), "sin mecanicas: la que pega mas")
            j.mecanicas = POSTURA
            self.assertEqual(j.elegir(mano, 1), ("jugar", 0), "con postura: la que la quita")
        self.assertEqual(j.razones, {"a.quita": ["quita la postura"]})


if __name__ == "__main__":
    unittest.main()

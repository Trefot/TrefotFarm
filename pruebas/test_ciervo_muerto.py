"""Ciervo Floor 4 (el usuario, 2026-11-24): "si se muere un personaje ya es mejor reiniciar". Y la fase 1 en
Automatico, siempre con todo."""
import unittest
from unittest import mock

import entorno  # noqa: F401  (antes que lumen)

from lumen.modos import MODOS
from lumen.vida_jefe import Vida


def modo(id_):
    m = MODOS[id_]({"victorias": 0, "extra": 0, "pociones": True, "max_pociones": 0})
    m.log = lambda *a, **k: None
    m._detectar_fase = lambda p, h: None
    m._reiniciar_por_bloqueo = lambda p: False
    return m


class CiervoMuerto(unittest.TestCase):
    def empezar(self, m, huecos):
        m.fase, m.turno_fase = 2, 1
        with mock.patch("lumen.vida_jefe.leer", return_value=Vida("azul", 0.8)), \
                mock.patch("lumen.juego.mano_bloqueada.esta", return_value=False):
            try:
                return m._empezar_turno(object(), huecos)
            except Exception:
                return "siguio"

    def test_con_3_cartas_reinicia(self):
        self.assertEqual(self.empezar(modo("ciervo_piso4"), 3), "rendirse")

    def test_con_4_cartas_sigue(self):
        self.assertNotEqual(self.empezar(modo("ciervo_piso4"), 4), "rendirse")

    def test_el_pajaro_no_cambia(self):
        self.assertNotEqual(self.empezar(modo("pajaro_piso4"), 3), "rendirse")

    def test_fase_1_automatico_con_todo_aunque_una_pelea_fuera_lenta(self):
        from lumen.ia import requisitos

        m = modo("ciervo_piso4")
        e = m.estrategia if hasattr(m, "estrategia") else m.clase_estrategia(m)
        e.estilo = requisitos.Estilo(requisitos.AUTOMATICO)
        e.estilo.fases_lentas.add(1)
        with mock.patch.object(e, "_golpe_maximo", return_value="todo") as golpe, \
                mock.patch.object(e, "_fase1", return_value="cautela"):
            self.assertEqual(e.guion(1, 1, 3, []), "todo")
        golpe.assert_called_once()


if __name__ == "__main__":
    unittest.main()

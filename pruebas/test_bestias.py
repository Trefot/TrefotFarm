"""Floor 1-3 de las bestias: estrategia simple, ciclo de pisos, navegacion y lectura de los pisos."""

import unittest
from unittest import mock

import entorno  # noqa: F401  (antes que lumen)
from entorno import PlantillaFalsa

from lumen import entrada, juego, ocr
from lumen.cartas import Carta, Rango, TipoCarta as T
from lumen.control import control
from lumen.modos import MODOS
from lumen.modos import bestias_pisos1a3 as B
from lumen.modos.catalogo import CATALOGO
from lumen.modos.perros_piso4 import PerrosPiso4, Reiniciar


def mano(*cs):
    return [Carta(posicion=i, tipo=t, rango=r) for i, (t, r) in enumerate(cs)]


class EstrategiaSimple(unittest.TestCase):
    def setUp(self):
        self.e = B.EstrategiaSimple()

    def test_ulti_primero(self):
        m = mano((T.NORMAL, Rango.BRONCE), (T.ULTI, Rango.ULTI), (T.NORMAL, Rango.ORO))
        self.assertEqual(self.e.decidir(1, 1, 0, m)[0], 1)

    def test_mas_rango_y_la_de_la_derecha(self):
        m = mano((T.NORMAL, Rango.ORO), (T.NORMAL, Rango.BRONCE), (T.NORMAL, Rango.ORO))
        self.assertEqual(self.e.decidir(1, 1, 0, m)[0], 2)

    def test_no_juega_bloqueadas(self):
        m = mano((T.NORMAL, Rango.PLATA), (T.BLOQUEADA, Rango.ORO), (T.NORMAL, Rango.BRONCE))
        self.assertEqual(self.e.decidir(1, 1, 0, m)[0], 0)

    def test_todo_bloqueado_mueve(self):
        m = mano((T.BLOQUEADA, Rango.ORO), (T.BLOQUEADA, Rango.ORO))
        self.assertEqual(self.e.decidir(1, 1, 0, m)[0], (1, 0))

    def test_sin_nada_reinicia(self):
        with self.assertRaises(Reiniciar):
            self.e.decidir(1, 1, 0, mano((T.SUELO, Rango.NINGUNO), (T.BLOQUEADA, Rango.ORO)))


class Catalogo(unittest.TestCase):
    def test_modos_listos(self):
        listos = {d.id for c in CATALOGO for d in c.destinos if d.id in MODOS}
        self.assertEqual(listos, {"perros_pisos1a3", "pajaro_pisos1a3", "ciervo_pisos1a3", "serpiente_pisos1a3",
                                  "rata_pisos1a3", "perros_piso4", "indura"})

    def test_bestias_y_pisos(self):
        destinos = {c.id: [d.nombre for d in c.destinos] for c in CATALOGO if c.grupo == "Bestias demoníacas"}
        self.assertEqual(list(destinos), ["pajaro", "ciervo", "perros", "serpiente", "rata", "surtr"])
        self.assertEqual(destinos["perros"], ["Floor 1-3", "Floor 4"])
        self.assertEqual(destinos["surtr"], ["Floor 1-3"])


class ConPantallaSimulada(unittest.TestCase):
    """Base: imagenes del juego falsas, clics anotados y OCR que devuelve ``self.texto``."""

    def setUp(self):
        for n in ("cancelar", "cerrar", "menu_batalla", "nido_criaturas", "pantalla_bestias", "ok", "empezar",
                  "carga_bestias", "piso3_superado"):
            self._parchear(juego, n, PlantillaFalsa(n))
        self.orden = [PlantillaFalsa(n) for n in ("pajaro", "ciervo", "perros", "serpiente", "rata")]
        self._parchear(juego, "ORDEN_BESTIAS", tuple(self.orden))
        self.arrastres, self.clics, self.texto, self.lecturas = [], [], [], 0
        self._parchear(entrada, "arrastrar", lambda d, h, o: self.arrastres.append((d, h)))
        self._parchear(entrada, "clic", lambda r, o, **k: self.clics.append(r))
        self._parchear(ocr, "disponible", lambda: True)
        self._parchear(ocr, "lineas_con_posicion", self._ocr)
        self._parchear(B, "CADA_OCR_S", 0)  # el texto cambia de una llamada a otra

    def _ocr(self, p, **_):
        self.lecturas += 1
        return [(t, (5, 5, 5, 5)) for t in self.texto]

    def _parchear(self, objeto, nombre, valor):
        parche = mock.patch.object(objeto, nombre, valor)
        parche.start()
        self.addCleanup(parche.stop)

    def modo(self, cls, valores=None, bestia=None):
        m = cls(valores or {})
        m.textos_vistos = True
        if bestia is not None:
            m.bestia = self.orden[bestia]
        return m


class Navegacion(ConPantallaSimulada):
    def test_desliza_a_la_derecha(self):
        m = self.modo(B.RataPisos1a3, bestia=4)
        self.assertIsNone(m.ir_a_perros({"pantalla_bestias", "pajaro"}, (0, 0)))
        self.assertEqual(self.arrastres[-1], (juego.COORD["deslizar_der"], juego.COORD["deslizar_izq"]))

    def test_desliza_a_la_izquierda(self):
        m = self.modo(B.PajaroPisos1a3, bestia=0)
        m.ir_a_perros({"pantalla_bestias", "serpiente"}, (0, 0))
        self.assertEqual(self.arrastres[-1], (juego.COORD["deslizar_izq"], juego.COORD["deslizar_der"]))

    def test_pantalla_de_pisos_por_el_texto(self):
        self.texto[:] = ["Floor 1", "Floor 2"]
        self.assertEqual(self.modo(B.RataPisos1a3, bestia=4).ir_a_perros(set(), (0, 0)), "elegir_piso")

    def test_pisos_aunque_siga_el_titulo_de_bestias(self):
        """En la pantalla de pisos sigue arriba "Demonic Beast Battle": basta con leer dos pisos."""
        self.texto[:] = ["Demonic Beast Battle", "Floor 3", "Floor 2"]
        m = self.modo(B.PajaroPisos1a3, bestia=0)
        self.assertEqual(m.ir_a_perros({"pantalla_bestias", "pajaro"}, (0, 0)), "elegir_piso")
        self.assertFalse(self.clics, "no vuelve a tocar al pajaro")

    def test_las_recompensas_no_son_la_pantalla_de_pisos(self):
        """La pantalla de elegir bestia lista "Obtain Floor 1 First Clear Reward"...: no son los pisos
        (en la prueba de la 0.2.1 el bot creia estar en los pisos y nunca entraba a la bestia)."""
        self.texto[:] = ["Demonic Beast Battle", "Skoll and Hati", "Obtain Floor 1 First Clear Reward",
                         "Obtain Floor 2 First Clear Reward", "Obtain Floor 3 First Clear Reward",
                         "Clear Twilight Temple Floor 3 to receive the guaranteed reward."]
        m = self.modo(B.PerrosPisos1a3, bestia=2)
        m.piso3_superado = PlantillaFalsa("piso3_superado")
        self.assertIsNone(m.ir_a_perros({"pantalla_bestias", "perros"}, (0, 0)))
        self.assertEqual(len(self.clics), 1, "toca a los perros para entrar")

    def test_lobos_objetivo_por_fase(self):
        """Floor 1-3 de los perros: fase 1 el perro claro (der), fases 2 y 3 el oscuro (izq)."""
        m = self.modo(B.PerrosPisos1a3, {"jugar": "Simple"})
        mano = [Carta(i, (0, 0, 1, 1), None, T.NORMAL, Rango.PLATA) for i in range(8)]
        self.assertEqual([m.estrategia.decidir(f, 1, 0, mano, 4)[1] for f in (1, 2, 3)], ["der", "izq", "izq"])
        self.assertIsNone(self.modo(B.PajaroPisos1a3, {"jugar": "Simple"}).estrategia.decidir(1, 1, 0, mano, 4)[1])

    def test_boton_por_texto_solo_seguros(self):
        """Pantallas sin imagen: toca OK/Receive..., nunca Cancel ni Shop."""
        m = self.modo(B.PerrosPisos1a3)
        self._parchear(ocr, "lineas_con_posicion", lambda p, **k: [("Cancel", (10, 10, 40, 10)), ("Shop", (10, 30, 40, 10))])
        self.assertEqual(m.clic_boton_por_texto(None, (0, 0)), "")
        self._parchear(ocr, "lineas_con_posicion", lambda p, **k: [("Cancel", (10, 10, 40, 10)), ("OK", (200, 800, 30, 12))])
        self.assertEqual(m.clic_boton_por_texto(None, (0, 0)), "OK")
        self.assertEqual(self.clics[-1], (215, 806))

    def test_floor_1_leido_como_i(self):
        """El lector de texto lee "Twilight Temple Floor 1" como "Floor I" (prueba de la 0.2.1)."""
        self.assertEqual(B.numeros_de_piso("Twilight Temple Floor I"), [1])
        self.assertEqual(B.numeros_de_piso("Floor l"), [1])
        self.assertEqual(B.numeros_de_piso("Floor Info"), [])
        self.texto[:] = ["Twilight Temple Floor 3", "Twilight Temple Floor 2", "Twilight Temple Floor I"]
        m = self.modo(B.PerrosPisos1a3, bestia=2)
        self.assertIsNone(m.elegir_piso(set(), (0, 0)))
        self.assertEqual(len(self.clics), 1, "toca el Floor 1")
        self.assertFalse(self.arrastres, "no hace falta deslizar")

    def test_cierra_el_aviso_al_abrir_la_bestia(self):
        m = self.modo(B.PajaroPisos1a3, bestia=0)
        self.assertIsNone(m.ir_a_perros({"pantalla_bestias", "pajaro", "ok"}, (0, 0)))
        self.assertEqual(len(self.clics), 1)

    def test_desliza_la_lista_hasta_ver_el_piso(self):
        m = self.modo(B.PajaroPisos1a3)
        m.piso = 1
        self.texto[:] = ["Floor 4", "Floor 3"]
        for _ in range(5):
            m._ultimo_desplazamiento = 0
            m.elegir_piso(set(), (0, 0))
        self.assertEqual(self.arrastres[:4], [B.DESPLAZAR_ABAJO] * 4)
        self.assertEqual(self.arrastres[4], B.DESPLAZAR_ARRIBA)
        self.texto[:] = ["Floor 2", "Floor 1"]
        m.elegir_piso(set(), (0, 0))
        self.assertTrue(self.clics, "abre el Floor 1 en cuanto lo ve")
        self.assertEqual(m._desplazamientos, 0)

    def test_piso_que_no_aparece_se_salta(self):
        m = self.modo(B.RataPisos1a3)
        m.piso = 3
        m.elegir_piso(set(), (0, 0))
        m.buscando_piso_desde -= B.SALTAR_PISO_S + 1
        m.elegir_piso(set(), (0, 0))
        self.assertEqual(m.piso, 1)
        self.texto[:] = ["Floor 1"]
        m.elegir_piso(set(), (0, 0))
        self.assertTrue(self.clics, "abre el Floor 1")

    def test_perros_reconoce_floor3_cleared(self):
        p = self.modo(B.PerrosPisos1a3)
        p.piso3_superado = juego.piso3_superado
        self.assertTrue(p._en_pisos({"piso3_superado"}))
        self.assertFalse(self.modo(B.RataPisos1a3)._en_pisos({"piso3_superado"}))


class Pisos(ConPantallaSimulada):
    def test_nombres_reales_de_los_pisos(self):
        r = self.modo(B.RataPisos1a3)
        for lineas, piso, encuentra in (
            (["Piso 3 del templo del ocaso", "Piso 2 del templo del ocaso", "Piso 1 del templo del ocaso"], 2, True),
            (["Salón del Génesis (piso 3)", "Salón del Génesis (piso 1)"], 1, True),
            (["Naglfar, la embarcación de los muertos (piso 2)"], 2, True),
            (["Twilight Temple Floor 1", "Floor 3 Cleared"], 3, False),
            (["Twilight Temple Floor 1", "Floor 3"], 3, True),
            (["FLOOR 2"], 2, True),
        ):
            with self.subTest(lineas=lineas, piso=piso):
                self.texto[:] = lineas
                r.piso = piso
                self.assertEqual(r._buscar_piso(None) is not None, encuentra)

    def test_ciclo_y_vueltas(self):
        publicado = []
        with mock.patch.object(control, "al_stats", publicado.append):
            m = self.modo(B.CiervoPisos1a3, {"primer_piso": "2"})
            self.assertEqual((m.stats["piso"], m.stats["vuelta"]), (2, 1))
            for esperado in ((3, 1), (1, 2), (2, 2)):
                m._siguiente_piso()
                self.assertEqual((publicado[-1]["piso"], publicado[-1]["vuelta"]), esperado)

    def test_victoria_pasa_al_siguiente_piso(self):
        m = self.modo(B.PerrosPisos1a3, {"primer_piso": "3"})
        with mock.patch.object(PerrosPiso4, "victoria", lambda self, p, o: "elegir_piso"):
            self.assertEqual(m.victoria(None, None), "elegir_piso")
        self.assertEqual(m.piso, 1)

    def test_ocr_como_mucho_una_vez_por_segundo(self):
        B.CADA_OCR_S = 1.0
        self.texto[:] = ["Floor 1"]
        m = self.modo(B.CiervoPisos1a3)
        for _ in range(5):
            m._buscar_piso(None)
        self.assertEqual(self.lecturas, 2)  # una lectura = 2 pasadas (normal e invertida)
        m._siguiente_piso()
        m._buscar_piso(None)
        self.assertEqual(self.lecturas, 4, "piso nuevo: se vuelve a leer")


if __name__ == "__main__":
    unittest.main()

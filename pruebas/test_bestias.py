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
                                  "perros_piso4", "demonio_rojo", "demonio_gris", "howlex",
                                  "bellmoth", "demonio_original", "indura", "oro", "monedas_sa"})

    def test_ratatoskr_cerrado_hasta_que_funcione(self):
        """El usuario lo cerro el 2026-11-09: sale en gris, pero el codigo sigue (y su botin viejo tiene nombre)."""
        from lumen.modos import CERRADOS, TODOS_LOS_MODOS

        self.assertIn("rata_pisos1a3", CERRADOS)
        self.assertNotIn("rata_pisos1a3", MODOS)
        self.assertIn("rata_pisos1a3", TODOS_LOS_MODOS)

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
        """Floor 1-3 de los perros: fase 1 el perro claro (der), fase 2 el oscuro (izq), fase 3 ninguno
        (los dos tienen que caer a la vez: areas y ultis)."""
        m = self.modo(B.PerrosPisos1a3, {"jugar": "Simple"})
        mano = [Carta(i, (0, 0, 1, 1), None, T.NORMAL, Rango.PLATA) for i in range(8)]
        self.assertEqual([m.estrategia.decidir(f, 1, 0, mano, 4)[1] for f in (1, 2, 3)], ["der", "izq", None])
        self.assertEqual(self.modo(B.PerrosPisos1a3, {"jugar": "Inteligente"}).estrategia.fases_area, frozenset({3}))
        self.assertIsNone(self.modo(B.PajaroPisos1a3, {"jugar": "Simple"}).estrategia.decidir(1, 1, 0, mano, 4)[1])

    def test_reset_tras_el_floor_3(self):
        """Tras el Floor 3 hay que pulsar Reset antes de volver al Floor 1."""
        m = self.modo(B.PerrosPisos1a3, bestia=2)
        m.piso = 3
        m._siguiente_piso()
        self.assertEqual((m.piso, m.pedir_reset), (1, True))
        self.texto[:] = ["Twilight Temple Floor 2", "Twilight Temple Floor 3", "Reset"]
        self.assertIsNone(m.elegir_piso(set(), (0, 0)))
        self.assertEqual(len(self.clics), 1, "pulsa Reset")
        self.assertFalse(m.pedir_reset)

    def test_boton_por_texto_solo_seguros(self):
        """Pantallas sin imagen: toca OK/Receive..., nunca Cancel ni Shop."""
        m = self.modo(B.PerrosPisos1a3)
        self._parchear(ocr, "lineas_con_posicion", lambda p, **k: [("Cancel", (10, 10, 40, 10)), ("Shop", (10, 30, 40, 10))])
        self.assertEqual(m.clic_boton_por_texto(None, (0, 0)), "")
        self._parchear(ocr, "lineas_con_posicion", lambda p, **k: [("Cancel", (10, 10, 40, 10)), ("OK", (200, 800, 30, 12))])
        self.assertEqual(m.clic_boton_por_texto(None, (0, 0)), "OK")
        self.assertEqual(self.clics[-1], (215, 806))

    def test_sesion_cerrada(self):
        """Avisos de sesion del juego: conexion duplicada se cierra y sigue; contrasena para el bot."""
        from lumen import avisos
        from lumen.motor import TerminarModo

        for n in ("reconectar", "reiniciar_juego", "conexion_duplicada", "conexion_caducada", "contrasena",
                  "servidor_global", "sync_data"):
            self._parchear(juego, n, PlantillaFalsa(n))
        enviados = []
        self._parchear(avisos, "enviar", lambda m, c=None: enviados.append(m))
        m = self.modo(B.PerrosPisos1a3)
        self.assertTrue(m.comprobaciones_globales({"conexion_duplicada", "ok"}, (0, 0)))
        self.assertEqual(len(self.clics), 1, "cierra el aviso con OK")
        self.assertTrue(m.comprobaciones_globales({"servidor_global"}, (0, 0)), "toca para volver a entrar")
        with self.assertRaises(TerminarModo):
            m.comprobaciones_globales({"contrasena"}, (0, 0))
        with self.assertRaises(TerminarModo):
            m.comprobaciones_globales({"sync_data"}, (0, 0))
        self.assertEqual(len(enviados), 3, "avisa al movil de la sesion cerrada, la contrasena y Sync Data")
        self.assertFalse(m.comprobaciones_globales(set(), (0, 0)))
        m.estado = "pelea"
        self.assertTrue(m.comprobaciones_globales({"reiniciar_juego"}, (0, 0)), "pulsa Restart en vez de parar")
        self.assertEqual(m.estado, m.estado_inicial(), "y empieza el modo desde el principio")

    def test_juego_cerrado_se_vuelve_a_abrir(self):
        """Si la ventana del juego desaparece, pulsa "Run Game" en el lanzador y empieza de nuevo."""
        from lumen import avisos, control as modulo_control, ventana

        self._parchear(juego, "abrir_juego", PlantillaFalsa("abrir_juego"))
        self._parchear(avisos, "enviar", lambda m, c=None: None)
        self._parchear(modulo_control.control, "esperar", lambda s: None)
        abierta = []
        self._parchear(ventana, "capturar_pantalla", lambda: (abierta.append(1) or {"abrir_juego"}, (0, 0)))
        self._parchear(ventana, "ventana_abierta", lambda: bool(abierta))
        self._parchear(ventana, "tamano_actual", lambda: (554, 960))
        self._parchear(ventana, "traer_al_frente", lambda: None)
        self._parchear(ventana, "ajustar_tamano", lambda: True)
        m = self.modo(B.PerrosPisos1a3)
        m.estado = "pelea"
        m._esperar_juego("No encuentro la ventana.")
        self.assertEqual(len(self.clics), 1, "pulsa Run Game una vez")
        self.assertEqual(m.estado, m.estado_inicial())

    def test_recuerda_el_piso_y_el_reset(self):
        """Al volver a arrancar sigue por el piso que tocaba y, tras el Floor 3, pulsa Reset primero."""
        from lumen import config

        config.guardar({"pisos_bestias": {}})
        m = self.modo(B.PajaroPisos1a3, bestia=0)
        m._siguiente_piso()
        self.assertEqual(self.modo(B.PajaroPisos1a3, bestia=0).piso, 2)
        m._siguiente_piso()
        m._siguiente_piso()  # despues del Floor 3: vuelta al 1 con Reset
        nuevo = self.modo(B.PajaroPisos1a3, bestia=0)
        self.assertEqual((nuevo.piso, nuevo.pedir_reset), (1, True))
        self.assertEqual(self.modo(B.CiervoPisos1a3, bestia=1).piso, 1, "cada bestia lleva su cuenta")
        config.guardar({"pisos_bestias": {}})

    def _pelea_con_huecos(self, lecturas):
        """Prepara una pelea donde cada lectura de pantalla da (huecos, segundos desde el inicio)."""
        from lumen import cartas as C
        from lumen.modos import perros_piso4 as P4

        m = self.modo(B.SerpientePisos1a3, bestia=3)
        empezados = []
        actual = {"huecos": 0, "t": 1000.0}
        self._parchear(m, "_empezar_turno", lambda p, h: empezados.append(h))
        self._parchear(m, "_talento_visible", lambda p: False)
        self._parchear(C, "contar_huecos", lambda p, u=0.8: actual["huecos"])
        self._parchear(P4.time, "time", lambda: actual["t"])
        for juego_falso in ("derrota", "cerrar", "victoria", "criatura_destruida", "piso3_superado", "saltar",
                            "mision_semanal", "info_mision"):
            self._parchear(juego, juego_falso, PlantillaFalsa(juego_falso))
        m._nueva_pelea()
        resultados = []
        for huecos, segundos in lecturas:
            actual["huecos"], actual["t"] = huecos, 1000.0 + segundos
            m.pelea(set(), (0, 0))
            resultados.append(list(empezados))
        return resultados

    def test_turno_con_pocos_huecos(self):
        """Nidhoggr y Ratatoskr dejan menos de 3 huecos: el turno empieza igual, tras 3 lecturas seguidas."""
        r = self._pelea_con_huecos([(2, 0), (2, 0.5), (2, 1.0)])
        self.assertEqual(r[1], [], "con 2 huecos no basta con 2 lecturas")
        self.assertEqual(r[2], [2])

    def test_turno_espera_a_que_salgan_todos_los_huecos(self):
        """PC lento (maquina virtual): los huecos aparecen poco a poco. No empieza con 2 si luego salen 4."""
        r = self._pelea_con_huecos([(2, 0), (2, 0.5), (4, 0.9), (4, 1.2), (4, 1.6)])
        self.assertEqual(r[2], [], "la cuenta cambio: vuelve a empezar a contar")
        self.assertEqual(r[3], [], "2 lecturas iguales, pero aun no lleva quieta el tiempo minimo")
        self.assertEqual(r[4], [4], "empieza con los 4 huecos")

    def test_turno_rapido_en_pc_normal(self):
        """En un PC normal (lecturas cada ~0,6 s) empieza a la 2.a lectura igual que antes."""
        r = self._pelea_con_huecos([(4, 0), (4, 0.6)])
        self.assertEqual(r[1], [4])

    def test_talento_en_el_turno_1(self):
        """El talento del equipo se toca al empezar el turno 1 de cada pelea, y solo entonces."""
        m = self.modo(B.SerpientePisos1a3, bestia=3)
        self._parchear(m, "_jugar_turno", lambda: None)
        self._parchear(m, "_detectar_fase", lambda p, h: None)
        self._parchear(m, "esperar_corto", lambda s: None)
        self._parchear(m, "capturar", lambda: (set(), (0, 0)))
        for n in ("mano_bloqueada",):
            self._parchear(juego, n, PlantillaFalsa(n))
        self._parchear(m, "_hay_talento", lambda p: False)
        m._empezar_turno(set(), 4)
        self.assertEqual(self.clics, [], "sin ningun heroe con talento no toca el boton (2026-11-09)")
        m.talento_inicial_usado, m.turno_fase, m.fase = False, 0, None
        self._parchear(m, "_hay_talento", lambda p: True)
        m._empezar_turno(set(), 4)
        self.assertEqual(self.clics, [juego.COORD["talento"]])
        m._empezar_turno(set(), 4)
        self.assertEqual(len(self.clics), 1, "en el turno 2 ya no")
        sin = self.modo(B.SerpientePisos1a3, {"talento": False}, bestia=3)
        self._parchear(sin, "_jugar_turno", lambda: None)
        self._parchear(sin, "_detectar_fase", lambda p, h: None)
        sin._empezar_turno(set(), 4)
        self.assertEqual(len(self.clics), 1, "con la opcion apagada no lo toca")

    def test_pasada_completa_acaba_con_reset(self):
        """Victorias cumplidas tras el Floor 3: pulsa Reset, confirma y para (antes paraba sin mas)."""
        from lumen import config
        from lumen.motor import TerminarModo
        from lumen.modos.perros_piso4 import PerrosPiso4

        config.guardar({"pisos_bestias": {}})

        def meta_cumplida(*a):
            raise TerminarModo()

        self._parchear(PerrosPiso4, "victoria", meta_cumplida)
        m = self.modo(B.PajaroPisos1a3, bestia=0)
        m.piso = 3
        self.assertEqual(m.victoria(set(), (0, 0)), "elegir_piso")
        self.assertTrue(m.pedir_reset and m.terminar_tras_reset)
        m.pedir_reset = False  # Reset ya pulsado
        with self.assertRaises(TerminarModo):
            m.elegir_piso({"ok"}, (0, 0))
        m2 = self.modo(B.PajaroPisos1a3, bestia=0)
        m2.piso, m2.pedir_reset = 1, False
        with self.assertRaises(TerminarModo, msg="a mitad de pasada para sin Reset"):
            m2.victoria(set(), (0, 0))
        self.assertEqual(self.modo(B.PajaroPisos1a3, bestia=0).piso, 2, "y apunta el piso siguiente")
        config.guardar({"pisos_bestias": {}})

    def test_piso_superado_se_salta(self):
        """Un piso ya superado no se abre: tras 3 toques pasa al siguiente (prueba de la 0.4.0: 40 s perdidos)."""
        self.texto[:] = ["Twilight Temple Floor 2", "Twilight Temple Floor 1"]
        m = self.modo(B.PerrosPisos1a3, bestia=2)
        for _ in range(B.TOQUES_PISO + 1):
            self.assertIsNone(m.elegir_piso(set(), (0, 0)))
        self.assertEqual(len(self.clics), B.TOQUES_PISO)
        self.assertEqual(m.piso, 2)

    def test_floor_1_leido_como_i(self):
        """El lector de texto lee "Twilight Temple Floor 1" como "Floor I" (prueba de la 0.2.1)."""
        self.assertEqual(B.numeros_de_piso("Twilight Temple Floor I"), [1])
        self.assertEqual(B.numeros_de_piso("Floor l"), [1])
        self.assertEqual(B.numeros_de_piso("Floor Info"), [])
        self.texto[:] = ["Twilight Temple Floor 3", "Twilight Temple Floor 2", "Twilight Temple Floor I"]
        m = self.modo(B.PerrosPisos1a3, bestia=2)
        self.assertIsNone(m.elegir_piso(set(), (0, 0)))
        self.assertEqual(len(self.clics), 1, "toca el Floor 1")
        self.assertEqual(self.clics[-1], (7, 7 + B.BAJO_TITULO), "en su circulo, no en el titulo (prueba de la 0.2.3)")
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


class DemoniosYFuerte(ConPantallaSimulada):
    def test_demonios_eligen_su_pestana(self):
        """Los 5 demonios de AutoFarming tocan su icono; Indura, su posicion y comprueba que quede elegida."""
        from lumen.modos import indura as D

        self._parchear(D, "VENTANA_UNION", PlantillaFalsa("union"))
        self._parchear(D, "NIVELES", {n: PlantillaFalsa(n) for n in D.NIVELES})
        gris = D.DemonioGris({})
        self._parchear(gris, "pestana", PlantillaFalsa("gris"))
        self.assertIsNone(gris.elegir({"union", "gris"}, (0, 0)))
        self.assertTrue(gris.pestana_elegida, "toca el icono y la da por elegida")
        self.assertEqual(gris.elegir({"union", "Hell"}, (0, 0)), "buscar", "nivel Hell y OK")
        self.assertEqual(gris.valores["jugar"], "AUTO")
        ind = D.Indura({})
        self._parchear(ind, "pestana_elegida_img", PlantillaFalsa("indura_elegida"))
        self.assertIsNone(ind.elegir({"union"}, (0, 0)))
        self.assertFalse(ind.pestana_elegida, "Indura no se da por elegida hasta verla")
        self.assertEqual(ind.elegir({"union", "indura_elegida", "Chaos"}, (0, 0)), "buscar")

    def test_monedas_sa_repite_si_el_cofre_es_peor(self):
        from lumen.modos import fuerte_solgres as F

        for n in ("VIDA_JEFE", "EMPEZAR", "REPETICION_TERMINADA", "VUELTA_TERMINADA", "MAZMORRA_FS", "ATRAS"):
            self._parchear(F, n, PlantillaFalsa(n))
        for n in ("pausa", "menu_batalla", "derrota"):
            self._parchear(juego, n, PlantillaFalsa(n))
        self._parchear(juego, "pocion_stamina", PlantillaFalsa("pocion"))
        m = F.MonedasSA({"cofre": "Plata"})
        self._parchear(m, "_cofre", lambda p: None)
        self.assertIsNone(m.pelea({"VIDA_JEFE", "pausa"}, (0, 0)), "el cofre aun no sale: espera, no repite")
        m.pelea_desde -= 999  # la pelea empezo hace rato y no hay cofre
        self.assertEqual(m.pelea({"VIDA_JEFE", "pausa"}, (0, 0)), "reintentar", "sin cofre se pierde material: repite")
        self.assertEqual((m.reinicios, m.sin_ver), (1, 1))
        m.reinicios = 0
        m._nueva_vuelta()
        self._parchear(m, "_cofre", lambda p: "Bronce")
        self.assertEqual(m.pelea(set(), (0, 0)), "reintentar", "el cofre se mira desde el principio: bronce, repite")
        m._nueva_vuelta()
        self.assertEqual(m.pelea({"VIDA_JEFE", "pausa"}, (0, 0)), "reintentar")
        self.assertEqual(m.reinicios, 2)
        self._parchear(m, "_cofre", lambda p: "Oro")
        self.assertIsNone(m.pelea({"VIDA_JEFE", "pausa"}, (0, 0)))
        self.assertEqual(m.cofres["Oro"], 1)

    def test_monedas_sa_repite_con_try_again(self):
        from lumen.modos import fuerte_solgres as F

        self._parchear(F, "REINTENTAR", PlantillaFalsa("try_again"))
        self._parchear(F, "CONFIRMAR_REINTENTAR", PlantillaFalsa("confirmar"))
        for n in ("MAZMORRA_FS", "ATRAS", "VUELTA_TERMINADA", "REPETICION_TERMINADA", "COFRE"):
            self._parchear(F, n, PlantillaFalsa(n))
        for n in ("menu_batalla", "derrota"):
            self._parchear(juego, n, PlantillaFalsa(n))
        self._parchear(juego, "pausa", PlantillaFalsa("pausa"))
        self._parchear(juego, "ok", PlantillaFalsa("ok"))
        m = F.MonedasSA({"cofre": "Oro"})
        m._repetir()
        self.assertIsNone(m.reintentar({"pausa"}, (0, 0)), "abre la pausa")
        self.assertIsNone(m.reintentar({"try_again"}, (0, 0)), "toca Try Again")
        self.assertEqual(len(self.clics), 2)
        self.assertIsNone(m.reintentar({"confirmar"}, (0, 0)), "confirma en la ventana que pregunta")
        self.assertEqual(len(self.clics), 3)
        self.assertEqual(m.reintentar({"pausa"}, (0, 0)), "pelea", "la pelea vuelve a empezar")
        otro = F.MonedasSA({"cofre": "Oro"})
        otro._repetir()
        for _ in range(F.INTENTOS_REINTENTAR):
            otro.reintentar({"pausa"}, (0, 0))
        self.assertEqual(otro.reintentar({"pausa"}, (0, 0)), "reiniciar", "sin Try Again: se rinde como antes")

    def test_monedas_sa_equipo_muerto(self):
        from lumen.modos import fuerte_solgres as F

        for n in ("REINTENTAR", "CONFIRMAR_REINTENTAR", "MAZMORRA_FS", "ATRAS", "REPETICION_TERMINADA", "VUELTA_TERMINADA",
                  "COFRE"):
            self._parchear(F, n, PlantillaFalsa(n))
        for n in ("pausa", "menu_batalla", "derrota"):
            self._parchear(juego, n, PlantillaFalsa(n))
        m = F.MonedasSA({"cofre": "Oro"})
        m._repetir()
        self.assertEqual(m.reintentar({"menu_batalla"}, (0, 0)), "ir", "ya en el menu: vuelve a entrar a la torre")
        self.assertEqual(m.derrotas, 1)
        fin = F.MonedasSA({})
        self._parchear(F, "EMPEZAR", PlantillaFalsa("start"))
        self.assertEqual(fin.fin({"start", "ok"}, (0, 0)), "preparar", "fin de la repeticion: de vuelta al Start")
        sola = F.MonedasSA({"cofre": "Oro"})
        sola._repetir()
        self.assertEqual(sola.reintentar({"REPETICION_TERMINADA"}, (0, 0)), "pelea", "acabo sola: sigue farmeando")
        buena = F.MonedasSA({"cofre": "Oro"})
        buena._repetir()
        self._parchear(buena, "_cofre", lambda p: "Oro")
        self.assertEqual(buena.reintentar({"pausa"}, (0, 0)), "pelea", "a ultima hora sale oro: no repite")
        self.assertEqual((buena.reinicios, buena.cofres["Oro"]), (0, 1))


class AutoEnBestiasFaciles(unittest.TestCase):
    """Pajaro, ciervo y perros (Floor 1-3) en AUTO por defecto: lo pidio el usuario (2026-11-08)."""

    def test_por_defecto_en_auto_solo_esas_tres(self):
        from lumen.modos import bestias_pisos1a3 as B

        self.assertTrue(B.PajaroPisos1a3({}).jugar_auto)
        self.assertTrue(B.CiervoPisos1a3({}).jugar_auto)
        self.assertTrue(B.PerrosPisos1a3({}).jugar_auto)
        self.assertFalse(B.SerpientePisos1a3({}).jugar_auto)
        self.assertFalse(B.PajaroPisos1a3({"jugar": "Inteligente"}).jugar_auto, "se puede elegir otra forma")

    def test_toca_auto_solo_si_las_casillas_no_se_llenan(self):
        from lumen.modos import bestias_pisos1a3 as B
        from lumen.modos import perros_piso4 as P4

        modo = B.PajaroPisos1a3({})
        modo._nueva_pelea()
        reloj, huecos, clics = [100.0], [4], []
        with mock.patch.object(P4.time, "time", lambda: reloj[0]), \
                mock.patch.object(P4.C, "contar_huecos", lambda p, u: huecos[0]), \
                mock.patch.object(modo, "clic_si", lambda pl, p, o, **k: clics.append(pl) or True), \
                mock.patch.object(modo, "log", lambda *a, **k: None):
            modo._pelea_auto(None, (0, 0))  # empiezan a contar 4 casillas libres
            reloj[0] = 102.0
            modo._pelea_auto(None, (0, 0))
            self.assertEqual(clics, [], "aun no: con AUTO ya puesto el juego las llena solo")
            reloj[0] = 104.5
            modo._pelea_auto(None, (0, 0))
            self.assertEqual(clics, [P4.AUTO], "4 s sin llenarse: el AUTO no esta puesto")
            self.assertTrue(modo.auto_puesto)
            huecos[0] = 3  # el juego ya juega solo
            reloj[0] = 106.0
            modo._pelea_auto(None, (0, 0))
            huecos[0] = 0
            reloj[0] = 120.0
            modo._pelea_auto(None, (0, 0))
            self.assertEqual(len(clics), 1, "no se vuelve a tocar mientras el juego juega")

    def test_quien_ya_tenia_inteligente_guardado_pasa_a_auto_una_vez(self):
        from lumen import config

        datos = {"opciones_modos": {"pajaro_pisos1a3": {"jugar": "Inteligente", "victorias": 3},
                                    "ciervo_pisos1a3": {"jugar": "Simple"},
                                    "serpiente_pisos1a3": {"jugar": "Inteligente"}}}
        config._auto_en_bestias_faciles(datos)
        o = datos["opciones_modos"]
        self.assertEqual(o["pajaro_pisos1a3"], {"jugar": "AUTO", "victorias": 3})
        self.assertEqual(o["ciervo_pisos1a3"]["jugar"], "Simple", "lo elegido a proposito se respeta")
        self.assertEqual(o["serpiente_pisos1a3"]["jugar"], "Inteligente")
        self.assertTrue(datos["auto_bestias_faciles"])


class ArreglosDelPlan(unittest.TestCase):
    """Lo que salio en el plan de 150 peleas del usuario (2026-11-09)."""

    def setUp(self):
        self.clics = []
        for nombre, valor in (("clic", lambda r, o, **k: self.clics.append(r)), ("arrastrar", lambda *a, **k: None)):
            p = mock.patch.object(entrada, nombre, valor)
            p.start()
            self.addCleanup(p.stop)

    def test_la_meta_son_vueltas_de_tres_pisos(self):
        m = B.RataPisos1a3({"victorias": 2})
        with mock.patch.object(m, "log", lambda *a, **k: None):
            m.piso = 1
            self.assertFalse(m._meta_cumplida())
            m.piso = 2
            self.assertFalse(m._meta_cumplida())
            m.piso = 3
            self.assertFalse(m._meta_cumplida(), "1 vuelta de 2")
            m.piso = 3
            self.assertTrue(m._meta_cumplida(), "2 vueltas")
        self.assertEqual(m.vueltas_hechas, 2)

    def test_tras_reset_espera_el_ok_sin_tocar_nada(self):
        m = B.RataPisos1a3({})
        m.esperando_ok_reset = __import__("time").time()
        ok = PlantillaFalsa("ok")
        with mock.patch.object(juego, "ok", ok), mock.patch.object(juego, "empezar", PlantillaFalsa("empezar")),                 mock.patch.object(m, "_buscar_piso", side_effect=AssertionError("no debe buscar ni deslizar")):
            self.assertIsNone(m.elegir_piso(set(), (0, 0)))  # aun sin OK: quieto
            self.assertIsNotNone(m.esperando_ok_reset)
            self.assertIsNone(m.elegir_piso({"ok"}, (0, 0)))
        self.assertIsNone(m.esperando_ok_reset, "OK pulsado: Reset hecho")

    def test_set_party_es_que_toca_el_floor_1(self):
        m = B.RataPisos1a3({})
        m.piso = 3
        with mock.patch.object(m, "_lineas", lambda p: [("Troublemaker's Hideout Floor 3", (0, 0, 9, 9)), ("Set Party", (0, 0, 9, 9))]),                 mock.patch.object(juego, "ok", PlantillaFalsa("ok")), mock.patch.object(juego, "empezar", PlantillaFalsa("empezar")),                 mock.patch.object(B.ocr, "disponible", lambda: True), mock.patch.object(m, "log", lambda *a, **k: None):
            m.elegir_piso(set(), (0, 0))
        self.assertEqual(m.piso, 1)

    def test_quita_el_auto_si_el_juego_juega_solo(self):
        from lumen.modos import perros_piso4 as P4

        m = B.RataPisos1a3({"jugar": "Inteligente"})
        m._nueva_pelea()
        m.ultimo_turno = 0
        lecturas = iter([4, 3, 2])
        with mock.patch.object(P4.C, "contar_huecos", lambda p, u: next(lecturas)),                 mock.patch.object(m, "clic_si", lambda pl, p, o, **k: self.clics.append(pl) or True),                 mock.patch.object(m, "log", lambda *a, **k: None):
            self.assertFalse(m._auto_puesto_sin_querer(None, (0, 0)))
            self.assertFalse(m._auto_puesto_sin_querer(None, (0, 0)), "una bajada puede ser casualidad")
            self.assertTrue(m._auto_puesto_sin_querer(None, (0, 0)))
        self.assertEqual(self.clics, [P4.AUTO])

    def test_victorias_guardadas_pasan_a_vueltas(self):
        from lumen import config

        datos = {"opciones_modos": {"pajaro_pisos1a3": {"victorias": 30}, "perros_piso4": {"victorias": 5}},
                 "plan": [{"modo": "rata_pisos1a3", "victorias": 30}, {"modo": "indura", "victorias": 4},
                          {"modo": "pajaro_pisos1a3", "victorias": 0}]}
        config._victorias_a_vueltas(datos)
        self.assertEqual(datos["opciones_modos"]["pajaro_pisos1a3"]["victorias"], 10)
        self.assertEqual(datos["opciones_modos"]["perros_piso4"]["victorias"], 5, "el Floor 4 sigue en peleas")
        self.assertEqual([t["victorias"] for t in datos["plan"]], [10, 4, 0])

    def test_nombre_de_los_lobos(self):
        self.assertEqual(B.PerrosPisos1a3.titulo_juego, "Skoll & Hati")


class AvisoTrasStart(unittest.TestCase):
    def test_tras_tres_start_sin_pelea_acepta_el_aviso(self):
        """Prueba del usuario (2026-11-09): un aviso tras Start dejaba al bot pulsando Start en bucle."""
        m = B.RataPisos1a3({})
        aceptados = []
        with mock.patch.object(juego, "empezar", PlantillaFalsa("empezar")), \
                mock.patch.object(juego, "pocion_stamina", PlantillaFalsa("pocion")), \
                mock.patch.object(juego, "carga_bestias", PlantillaFalsa("carga")), \
                mock.patch.object(juego, "carga_taberna", PlantillaFalsa("carga_t")), \
                mock.patch.object(juego, "ok", PlantillaFalsa("ok")), \
                mock.patch.object(m, "clic_si", lambda pl, p, o, **k: pl.esta(p)), \
                mock.patch.object(m, "_aceptar_aviso", lambda p, o: aceptados.append(1)):
            m.equipo_verificado = True
            for _ in range(2):
                m.preparar({"empezar"}, (0, 0))
            self.assertEqual(aceptados, [], "las dos primeras veces solo Start")
            m.preparar({"empezar"}, (0, 0))
            self.assertEqual(aceptados, [1])
            m.preparar(set(), (0, 0))  # Start ya no se ve: el aviso lo tapa
            self.assertEqual(len(aceptados), 2)


class AvisoReinicioSemanal(unittest.TestCase):
    def test_primero_el_ok_y_no_start(self):
        """"Demonic Beast Battle will have its weekly reset soon. Proceed anyway?": Start se ve detras."""
        m = B.SerpientePisos1a3({})
        m.equipo_verificado = True
        clics = []
        with mock.patch.object(juego, "empezar", PlantillaFalsa("empezar")), \
                mock.patch.object(juego, "ok", PlantillaFalsa("ok")), \
                mock.patch.object(juego, "pocion_stamina", PlantillaFalsa("pocion")), \
                mock.patch.object(m, "clic_si", lambda pl, p, o, **k: pl.esta(p) and (clics.append(pl.nombre) or True)), \
                mock.patch.object(m, "log", lambda *a, **k: None):
            m.preparar({"empezar", "ok"}, (0, 0))
        self.assertEqual(clics, ["ok"], "acepta el aviso y no toca Start debajo")


class PisoAbierto(unittest.TestCase):
    """El piso abierto lleva una flecha cian a la izquierda; los cerrados salen oscuros (usuario, 2026-11-09)."""

    def setUp(self):
        import cv2
        from pathlib import Path

        self.p = cv2.imread(str(Path(__file__).with_name("pisos_nidhoggr.png")))  # Nidhoggr con el Floor 1 abierto

    def test_ve_la_flecha_del_floor_1(self):
        import numpy as np

        m = B.SerpientePisos1a3({})
        flechas = m.flechas_piso_abierto(self.p)
        self.assertEqual(len(flechas), 1)
        self.assertLess(abs(flechas[0] - 680), 8)
        self.assertEqual(m.flechas_piso_abierto(np.zeros_like(self.p)), [], "sin flecha: todo superado o cerrado")

    def test_con_el_floor_4_abierto_hay_dos_flechas_y_elige_la_del_floor_1_3(self):
        """Lo aviso el usuario: si el Floor 4 (Transcendent) esta abierto tambien lleva flecha."""
        m = B.SerpientePisos1a3({})
        p = self.p.copy()
        p[230:260] = p[665:695]  # la misma fila de la flecha, arriba: la del Transcendent
        self.assertEqual(len(m.flechas_piso_abierto(p)), 2)
        clics = []
        lineas = [("Transcendent Nidhoggr", (190, 190, 180, 18)), ("Corpse Farer Naglfar Floor 1", (190, 616, 180, 18))]
        with mock.patch.object(entrada, "clic", lambda r, o, **k: clics.append(r)),                 mock.patch.object(B.ocr, "disponible", lambda: True), mock.patch.object(m, "_lineas", lambda p: lineas),                 mock.patch.object(m, "_recordar_piso", lambda: None), mock.patch.object(m, "log", lambda *a, **k: None):
            self.assertTrue(m._ir_al_piso_abierto(p, (0, 0)))
        self.assertLess(abs(clics[0][1] - 680), 8, "la del Floor 1, no la del Transcendent")

    def test_va_directo_al_abierto_aunque_esperara_otro(self):
        m = B.SerpientePisos1a3({})
        m.piso = 3
        clics = []
        lineas = [("Corpse Farer Naglfar Floor 3", (190, 318, 180, 18)), ("Corpse Farer Naglfar Floor 2", (190, 467, 180, 18)),
                  ("Corpse Farer Naglfar Floor 1", (190, 616, 180, 18))]
        with mock.patch.object(entrada, "clic", lambda r, o, **k: clics.append(r)), \
                mock.patch.object(B.ocr, "disponible", lambda: True), mock.patch.object(m, "_lineas", lambda p: lineas), \
                mock.patch.object(m, "_recordar_piso", lambda: None), mock.patch.object(m, "log", lambda *a, **k: None):
            self.assertTrue(m._ir_al_piso_abierto(self.p, (0, 0)))
        self.assertEqual(m.piso, 1)
        self.assertEqual(len(clics), 1)
        self.assertLess(abs(clics[0][1] - 680), 8, "toca el retrato del Floor 1")


class CarruselDeBestias(unittest.TestCase):
    def setUp(self):
        self.arrastres = []
        p = mock.patch.object(entrada, "arrastrar", lambda a, b, o, **k: self.arrastres.append((a, b)))
        p.start()
        self.addCleanup(p.stop)
        for b in juego.ORDEN_BESTIAS:
            q = mock.patch.object(b, "esta", lambda p, u=0.7: False)
            q.start()
            self.addCleanup(q.stop)

    def test_en_surtr_vuelve_hacia_atras(self):
        """Surtr es la ultima y no tiene imagen: el bot deslizaba sin fin hacia el final (2026-11-09)."""
        m = B.CiervoPisos1a3({})
        with mock.patch.object(B.ocr, "disponible", lambda: True), \
                mock.patch.object(B.ocr, "lineas_con_posicion", lambda p: [("Surtr and the Primordial Flame", (0, 0, 9, 9))]):
            m._deslizar_hacia_bestia(None, (0, 0))
        self.assertEqual(self.arrastres, [(juego.COORD["deslizar_izq"], juego.COORD["deslizar_der"])], "hacia atras")

    def test_sin_saber_donde_esta_va_y_vuelve(self):
        m = B.CiervoPisos1a3({})
        with mock.patch.object(B.ocr, "disponible", lambda: False):
            for _ in range(12):
                m._deslizar_hacia_bestia(None, (0, 0))
        self.assertEqual(len(set(self.arrastres)), 2, "cambia de direccion")


class PisosDeOtraBestia(unittest.TestCase):
    def test_en_los_pisos_del_dragon_y_se_pide_la_rata_vuelve_atras(self):
        """Prueba del usuario (2026-11-09): el juego estaba en el dragon, se pidio la rata y abria los del dragon."""
        m = B.RataPisos1a3({})
        clics = []
        with mock.patch.object(m, "_en_pisos", lambda p: True), \
                mock.patch.object(B.ocr, "disponible", lambda: True), \
                mock.patch.object(B.ocr, "lineas_con_posicion", lambda p: [("Nidhoggr", (236, 137, 81, 19))]), \
                mock.patch.object(m, "clic_si", lambda pl, p, o, **k: pl is B.ATRAS and (clics.append(pl) or True)), \
                mock.patch.object(juego, "cancelar", PlantillaFalsa("cancelar")), mock.patch.object(m, "log", lambda *a, **k: None):
            self.assertIsNone(m.ir_a_perros(set(), (0, 0)))
        self.assertEqual(clics, [B.ATRAS])

    def test_en_sus_propios_pisos_sigue(self):
        m = B.SerpientePisos1a3({})
        with mock.patch.object(m, "_en_pisos", lambda p: True), \
                mock.patch.object(B.ocr, "disponible", lambda: True), \
                mock.patch.object(B.ocr, "lineas_con_posicion", lambda p: [("Nidhoggr", (236, 137, 81, 19))]), \
                mock.patch.object(juego, "cancelar", PlantillaFalsa("cancelar")), mock.patch.object(m, "log", lambda *a, **k: None):
            self.assertEqual(m.ir_a_perros(set(), (0, 0)), "elegir_piso")


class PisoAbiertoSinTitulo(unittest.TestCase):
    def test_floor_3_sin_leer_su_titulo(self):
        """El titulo del piso abierto (resaltado) no se leia: se deduce de los demas (dragon, 2026-11-09)."""
        import cv2
        from pathlib import Path

        p = cv2.imread(str(Path(__file__).with_name("pisos_nidhoggr_f3.png")))
        m = B.SerpientePisos1a3({})
        m.piso = 1
        clics = []
        lineas = [("Corpse Farer Naglfar Floor 2", (195, 471, 177, 13)), ("Corpse Farer Naglfar Floor I", (197, 620, 174, 13))]
        with mock.patch.object(entrada, "clic", lambda r, o, **k: clics.append(r)), \
                mock.patch.object(B.ocr, "disponible", lambda: True), mock.patch.object(m, "_lineas", lambda p: lineas), \
                mock.patch.object(m, "_recordar_piso", lambda: None), mock.patch.object(m, "log", lambda *a, **k: None):
            self.assertTrue(m._ir_al_piso_abierto(p, (0, 0)))
        self.assertEqual(m.piso, 3)
        self.assertLess(abs(clics[0][1] - 383), 8)


class SinRendirseEnPisos1a3(unittest.TestCase):
    def test_mueve_cualquier_par_aunque_haya_huecos(self):
        """La rata (2026-11-09): 3 cartas bloqueadas separadas por huecos; el bot no encontraba pareja y se rendia."""
        mano = [Carta(i, tipo=T.SUELO) for i in range(8)]
        for i in (3, 5, 7):
            mano[i] = Carta(i, tipo=T.BLOQUEADA, rango=Rango.BRONCE)
        idx, _, _ = B.EstrategiaSimple().decidir(2, 2, 2, mano, 4)
        self.assertEqual(idx, (5, 3))

    def test_sin_jugada_espera_en_vez_de_rendirse(self):
        m = B.RataPisos1a3({})
        self.assertFalse(m.rendirse_si_bloqueada)


class RecompensaDelReto(unittest.TestCase):
    """Challenge Reward (2026-11-09): tras el Floor 3 brilla arriba a la izquierda y se toca para recogerla."""

    def leer(self, nombre):
        import cv2
        from pathlib import Path

        return cv2.imread(str(Path(__file__).with_name(f"{nombre}.png")))

    def test_brilla_tras_el_floor_3_y_no_antes(self):
        m = B.PajaroPisos1a3({})
        self.assertTrue(m.reto_brilla(self.leer("reto_021734")))
        self.assertFalse(m.reto_brilla(self.leer("reto_021807")), "otra bestia sin la vuelta hecha")

    def test_lo_toca_una_vez_y_apunta_lo_que_da(self):
        m = B.PajaroPisos1a3({})
        m.reto_por_recoger = True
        clics, fotos = [], []
        with mock.patch.object(entrada, "clic", lambda r, o, **k: clics.append(r)), \
                mock.patch.object(m, "guardar_recompensa", lambda p, v, primera=False: fotos.append(primera)), \
                mock.patch.object(m, "log", lambda *a, **k: None):
            self.assertIsNone(m.elegir_piso(self.leer("reto_021734"), (0, 0)))
            self.assertEqual(clics, [B.PUNTO_RETO])
            self.assertFalse(m.reto_por_recoger, "una sola vez")
            m.elegir_piso(self.leer("reward_notification"), (0, 0))
        self.assertEqual(fotos, [True], "la recompensa se apunta en el Botin")
        self.assertEqual(clics[-1], B.PUNTO_CONTINUAR)


class DondeEstaLaRata(unittest.TestCase):
    """La rata tapa la espiral cian del tronco al que esta subida (2026-11-09)."""

    def leer(self, nombre):
        import cv2
        from pathlib import Path

        return cv2.imread(str(Path(__file__).with_name(f"{nombre}.png")))

    def test_en_el_centro_y_a_la_derecha(self):
        m = B.RataPisos1a3({})
        self.assertEqual(m.donde_rata(self.leer("rata_centro")), B.RataPisos1a3.ESPIRALES["centro"][1])
        self.assertEqual(m.donde_rata(self.leer("rata_derecha")), B.RataPisos1a3.ESPIRALES["der"][1])

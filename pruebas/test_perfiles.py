"""Aislamiento de memorias, politicas acotadas y restauracion autorizada."""

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import entorno  # noqa: F401
from lumen import admin
from lumen.control import control
from lumen.ia import aprendizaje as A, perfiles as P, lecciones as L

EQUIPO = ["a", "b", "c", "d"]
OTRO = ["a", "b", "c", "e"]


class Perfiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for parche in (
            mock.patch.object(P, "CARPETA", Path(self.tmp.name)),
            mock.patch.object(admin, "activo", return_value=True),
        ):
            parche.start()
            self.addCleanup(parche.stop)
        self.addCleanup(setattr, control, "ejecutando", False)
        control.ejecutando = False

    def pelea(self, equipo=EQUIPO, destino="ciervo_f1", resultado="victoria", **extra):
        extra.setdefault("conocimiento", P.firma_conocimiento())
        return dict(
            destino=destino,
            equipo=equipo,
            resultado=resultado,
            inicio=time.time(),
            duracion=100,
            config=dict(A.DEFECTO),
            turnos=[
                dict(fase=1, turno=1, confirmada=True, jugada=["jugar", "a.skill_1"])
            ],
            **extra,
        )

    def test_clave_equipo_independiente_del_orden(self):
        self.assertEqual(
            P.clave("ciervo_f1", EQUIPO), P.clave("ciervo_f1", list(reversed(EQUIPO)))
        )
        self.assertNotEqual(P.clave("ciervo_f1", EQUIPO), P.clave("ciervo_f2", EQUIPO))
        self.assertNotEqual(P.clave("ciervo_f1", EQUIPO), P.clave("ciervo_f1", OTRO))

    def test_equipo_incompleto_o_rutas_no_se_aceptan(self):
        for equipo in ([], ["a", "b"], ["a", "a", "b"], ["../a", "b", "c"]):
            self.assertIsNone(P.carpeta("ciervo_f1", equipo))
        self.assertIsNone(P.carpeta("../../fuera", EQUIPO))

    def test_lecciones_no_saltan_entre_equipos(self):
        self.assertTrue(P.aprender(self.pelea()))
        carpeta = P.carpeta("ciervo_f1", EQUIPO)
        self.assertGreater(
            L.aplicar({"a.skill_1": 1}, "ciervo_f1", 1, carpeta=carpeta)[0][
                "a.skill_1"
            ],
            1,
        )
        self.assertEqual(P.estado("ciervo_f1", OTRO)["lecciones"], {})
        self.assertEqual(P.estado("ciervo_f2", EQUIPO)["lecciones"], {})

    def test_sin_equipo_no_guarda_lecciones(self):
        self.assertEqual(P.aprender(self.pelea(equipo=[])), [])
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])

    def test_filtra_destino_equipo_y_calidad(self):
        buena = self.pelea()
        filas = [
            buena,
            self.pelea(equipo=OTRO),
            self.pelea(destino="ciervo_f2"),
            self.pelea(calidad="incierta"),
        ]
        self.assertEqual(P.filtrar(filas, "ciervo_f1", EQUIPO), [buena])

    def test_no_entrena_con_acciones_sin_confirmar_o_base_distinta(self):
        pelea = self.pelea(memoria_por_equipo=True, conocimiento=P.firma_conocimiento())
        self.assertEqual(P.filtrar([pelea], "ciervo_f1", EQUIPO), [pelea])
        sin = {**pelea, "turnos": [{"confirmada": False}]}
        vieja = {**pelea, "conocimiento": "anterior"}
        self.assertEqual(P.filtrar([sin, vieja], "ciervo_f1", EQUIPO), [])

    def test_copiar_reiniciar_restaurar(self):
        P.aprender(self.pelea())
        anterior = P.estado("ciervo_f1", EQUIPO)["lecciones"]
        nombre = P.guardar_copia("ciervo_f1", EQUIPO)
        P.restaurar("ciervo_f1", EQUIPO, None)
        self.assertEqual(P.estado("ciervo_f1", EQUIPO)["lecciones"], {})
        P.restaurar("ciervo_f1", EQUIPO, nombre)
        self.assertEqual(P.estado("ciervo_f1", EQUIPO)["lecciones"], anterior)
        self.assertGreaterEqual(len(P.copias("ciervo_f1", EQUIPO)), 3)

    def test_reinicio_no_reincorpora_estadisticas_antiguas(self):
        vieja = self.pelea()
        P.restaurar("ciervo_f1", EQUIPO, None)
        self.assertEqual(P.filtrar([vieja], "ciervo_f1", EQUIPO), [])
        self.assertEqual(P.aprender(vieja), [])

    def test_restaurar_requiere_llave_y_bot_detenido(self):
        with mock.patch.object(admin, "activo", return_value=False):
            with self.assertRaises(PermissionError):
                P.restaurar("ciervo_f1", EQUIPO, None)
        control.ejecutando = True
        with self.assertRaises(RuntimeError):
            P.restaurar("ciervo_f1", EQUIPO, None)
        control.ejecutando = False
        with self.assertRaises(RuntimeError):
            P.guardar_copia("ciervo_f1", EQUIPO, ocupado=True)

    def test_no_acepta_ruta_ni_copia_de_otro_equipo(self):
        with self.assertRaises(ValueError):
            P.restaurar("ciervo_f1", EQUIPO, "../otro.json")
        nombre = P.guardar_copia("ciervo_f1", EQUIPO)
        ruta = P.carpeta("ciervo_f1", EQUIPO) / nombre
        datos = json.loads(ruta.read_text())
        datos["equipo"] = OTRO
        ruta.write_text(json.dumps(datos))
        with self.assertRaises(ValueError):
            P.restaurar("ciervo_f1", EQUIPO, nombre)

    def test_rechaza_pesos_fuera_de_limites(self):
        nombre = P.guardar_copia("ciervo_f1", EQUIPO)
        ruta = P.carpeta("ciervo_f1", EQUIPO) / nombre
        datos = json.loads(ruta.read_text())
        datos["lecciones"] = {"fases": {"1": {"carta:a.skill_1": {"peso": 50}}}}
        ruta.write_text(json.dumps(datos))
        with self.assertRaises(ValueError):
            P.restaurar("ciervo_f1", EQUIPO, nombre)

    def test_error_de_escritura_suspende_aprendizaje_hasta_recuperar(self):
        P.aprender(self.pelea())
        escribir = P.escribir_texto

        def fallo(ruta, texto, **kwargs):
            if ruta.name == "ciervo_f1.json":
                raise OSError("disco lleno")
            return escribir(ruta, texto, **kwargs)

        with mock.patch.object(P, "escribir_texto", side_effect=fallo):
            with self.assertRaises(OSError):
                P.restaurar("ciervo_f1", EQUIPO, None)
        self.assertFalse(P.habilitado("ciervo_f1", EQUIPO))
        self.assertEqual(P.filtrar([self.pelea()], "ciervo_f1", EQUIPO), [])
        self.assertEqual(P.aprender(self.pelea()), [])
        P.restaurar("ciervo_f1", EQUIPO, None)
        self.assertTrue(P.habilitado("ciervo_f1", EQUIPO))

    def test_explorar_solo_despues_de_base_medida(self):
        with mock.patch.object(A, "elegir", return_value=(A.DEFECTO, False)) as elegir:
            P.elegir([], "ciervo_f1", EQUIPO)
            self.assertFalse(elegir.call_args.kwargs["explorar"])
            P.elegir([self.pelea() for _ in range(5)], "ciervo_f1", EQUIPO)
            self.assertTrue(elegir.call_args.kwargs["explorar"])

    def test_no_adopta_variante_menos_fiable_aunque_sea_rapida(self):
        rapido = {**A.DEFECTO, "valor_ulti": 5.0}
        base = [{**self.pelea(), "duracion": 100} for _ in range(5)]
        variante = [
            {**self.pelea(), "config": rapido, "duracion": 20} for _ in range(4)
        ]
        variante.append({**variante[0], "resultado": "derrota"})
        self.assertEqual(A.base(base + variante), A.DEFECTO)

    def test_parametros_invalidos_no_cuentan(self):
        for config in ({"valor_ulti": 999}, {**A.DEFECTO, "valor_ulti": float("nan")}):
            self.assertEqual(A.cifras([{**self.pelea(), "config": config}]), {})
        self.assertEqual(A.cifras([{**self.pelea(), "duracion": 0}]), {})

    def test_jugador_aplica_memoria_solo_al_equipo_indicado(self):
        from lumen import inteligencia as I
        from lumen.cartas import Carta, Rango, TipoCarta

        P.aprender(self.pelea())
        mano = [
            Carta(0, tipo=TipoCarta.NORMAL, rango=Rango.BRONCE, nombre="a.skill_1"),
            Carta(1, tipo=TipoCarta.NORMAL, rango=Rango.BRONCE, nombre="b.skill_1"),
        ]
        j = I.Jugador()
        j.destino, j.fase, j.equipo = "ciervo_f1", 1, EQUIPO
        j._tasador = mock.Mock(
            valores=lambda ns: {n: 1 for n in ns}, es_area=lambda n: False
        )
        j._indice = mock.Mock()
        with mock.patch.object(I, "agrupar_por_dibujo"):
            j.usar_aprendizaje = False
            self.assertEqual(j.elegir(mano, 1), ("jugar", 1))
            j.usar_aprendizaje = True
            self.assertEqual(j.elegir(mano, 1), ("jugar", 0))
            j.equipo = OTRO
            self.assertEqual(j.elegir(mano, 1), ("jugar", 1))
            j.equipo = ()
            self.assertEqual(j.elegir(mano, 1), ("jugar", 1))

    def test_perfil_corrupto_no_tumba_el_bot(self):
        ruta = P.preparar("ciervo_f1", EQUIPO)
        (ruta / "perfil.json").write_text("{roto")
        self.assertFalse(P.habilitado("ciervo_f1", EQUIPO))
        self.assertEqual(P.filtrar([self.pelea()], "ciervo_f1", EQUIPO), [])
        self.assertEqual(P.parametros("ciervo_f1", EQUIPO), A.DEFECTO)

    def test_copia_restaurada_conserva_parametros(self):
        ruta = P.preparar("ciervo_f1", EQUIPO)
        meta = json.loads((ruta / "perfil.json").read_text())
        parametros = {**A.DEFECTO, "valor_ulti": 5.0}
        meta["parametros"] = parametros
        (ruta / "perfil.json").write_text(json.dumps(meta))
        nombre = P.guardar_copia("ciervo_f1", EQUIPO)
        P.restaurar("ciervo_f1", EQUIPO, None)
        self.assertEqual(P.parametros("ciervo_f1", EQUIPO), A.DEFECTO)
        P.restaurar("ciervo_f1", EQUIPO, nombre)
        self.assertEqual(P.parametros("ciervo_f1", EQUIPO), parametros)

    def test_floor4_conecta_con_las_fichas_de_jefe(self):
        from lumen.modos.bestias_piso4 import EstrategiaPajaro4, EstrategiaCiervo4
        from lumen.ia import decidir

        self.assertTrue(decidir.mecanicas_de(EstrategiaPajaro4.destino, 2))
        self.assertTrue(decidir.mecanicas_de(EstrategiaCiervo4.destino, 4))


if __name__ == "__main__":
    unittest.main()

"""Modo administrador con contrasena: en el repositorio solo la huella (2026-11-09)."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import entorno  # noqa: F401  (antes que lumen)

from lumen import admin, config


class Admin(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.guardado = {"modo_admin": True, "admin_llave": ""}  # la casilla vieja marcada, sin contrasena
        parches = [
            mock.patch.object(admin, "ARCHIVO", self.dir / "admin.yaml"),
            mock.patch.object(admin, "HUELLA_LOCAL", self.dir / "huella_admin.txt"),
            mock.patch.object(admin, "VUELTAS", 1000),  # rapido en las pruebas
            mock.patch.object(config, "obtener_guardado", lambda c, d=None: self.guardado.get(c, d)),
            mock.patch.object(config, "guardar", lambda cambios: self.guardado.update(cambios)),
        ]
        for p in parches:
            p.start()
            self.addCleanup(p.stop)

    def publicar(self):
        (self.dir / "admin.yaml").write_text((self.dir / "huella_admin.txt").read_text(encoding="utf-8"), encoding="utf-8")

    def test_la_casilla_sola_no_basta(self):
        self.assertFalse(admin.activo(), "sin contrasena publicada no hay admin")

    def test_crear_publicar_y_entrar(self):
        texto = admin.crear("una contraseña larga")
        self.assertNotIn("contraseña larga", texto, "solo la huella, nunca la contrasena")
        self.assertFalse(admin.desbloqueado(), "hasta que la huella se publique")
        self.publicar()
        self.assertTrue(admin.desbloqueado(), "esta PC tiene la llave")
        self.assertTrue(admin.activo())

    def test_otra_pc_necesita_la_contrasena(self):
        admin.crear("una contraseña larga")
        self.publicar()
        self.guardado.update({"admin_llave": "", "modo_admin": False})  # la PC de un amigo con el link
        self.assertFalse(admin.activo())
        self.assertFalse(admin.entrar("otra cosa"))
        self.assertFalse(admin.activo())
        self.assertTrue(admin.entrar("una contraseña larga"))
        self.assertTrue(admin.activo())
        admin.salir()
        self.assertFalse(admin.activo())

    def test_crearla_en_otra_pc_no_sirve(self):
        admin.crear("una contraseña larga")
        self.publicar()
        admin.crear("la del amigo 12345")  # se crea su propia llave, pero la huella publicada es otra
        self.assertFalse(admin.desbloqueado())

    def test_contrasena_corta(self):
        with self.assertRaises(ValueError):
            admin.crear("corta")


if __name__ == "__main__":
    unittest.main()

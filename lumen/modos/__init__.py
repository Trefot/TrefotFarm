"""Registro de modos. Para agregar uno nuevo: crea el archivo y anadelo a MODOS."""

from lumen.modos.perros_piso4 import PerrosPiso4

MODOS = {m.id: m for m in (PerrosPiso4,)}

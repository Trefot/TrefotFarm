"""Registro de modos. Para agregar uno nuevo: crea el archivo y anadelo a MODOS."""

from lumen.modos.perros_piso4 import PerrosPiso4
from lumen.modos.perros_pisos_bajos import PerrosPiso1, PerrosPiso2, PerrosPiso3

MODOS = {m.id: m for m in (PerrosPiso4, PerrosPiso1, PerrosPiso2, PerrosPiso3)}

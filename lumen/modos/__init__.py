"""Registro de modos. Para agregar uno nuevo: crea el archivo y anadelo a MODOS."""

from lumen.modos.indura import Indura
from lumen.modos.perros_piso4 import PerrosPiso4
from lumen.modos.perros_pisos_bajos import PerrosPisos1a3

MODOS = {m.id: m for m in (PerrosPisos1a3, PerrosPiso4, Indura)}

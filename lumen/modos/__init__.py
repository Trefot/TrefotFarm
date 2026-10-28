"""Registro de modos. Para agregar uno nuevo: crea el archivo y anadelo a MODOS."""

from lumen.modos.indura import Indura
from lumen.modos.perros_piso4 import PerrosPiso4
from lumen.modos import bestias_pisos1a3

MODOS = {m.id: m for m in (*bestias_pisos1a3.TODAS, PerrosPiso4, Indura)}

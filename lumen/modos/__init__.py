"""Registro de modos. Para agregar uno nuevo: crea el archivo y anadelo a MODOS."""

from lumen.modos.perros_piso4 import PerrosPiso4
from lumen.modos import bestias_pisos1a3, fuerte_solgres, indura

MODOS = {m.id: m for m in (*bestias_pisos1a3.TODAS, PerrosPiso4, *indura.TODOS, *fuerte_solgres.TODOS)}

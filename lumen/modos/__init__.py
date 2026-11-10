"""Registro de modos. Para agregar uno nuevo: crea el archivo y anadelo a MODOS."""

from lumen.modos.perros_piso4 import PerrosPiso4
from lumen.modos import bestias_piso4, bestias_pisos1a3, fuerte_solgres, indura

# Todos los que existen en el codigo (para nombres de recompensas viejas, pruebas...).
TODOS_LOS_MODOS = {m.id: m for m in (*bestias_pisos1a3.TODAS, PerrosPiso4, *bestias_piso4.TODOS, *indura.TODOS, *fuerte_solgres.TODOS)}

# Cerrados hasta que funcionen bien: salen en gris ("proximamente") y no se pueden empezar ni poner en el plan.
# Ratatoskr: el usuario lo cerro el 2026-11-09 (las mecanicas de los pisos 1-3 aun fallan en el juego).
CERRADOS = {"rata_pisos1a3"}

MODOS = {k: m for k, m in TODOS_LOS_MODOS.items() if k not in CERRADOS}

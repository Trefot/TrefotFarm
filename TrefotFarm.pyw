"""Puente de la version 2 (temporal): abre LumenFarm.pyw.

Lo usan el reinicio tras actualizar desde una version 2.x y los accesos directos viejos.
Al abrirse, la version nueva cambia esos accesos por los de "Lumen Farm". Despues se borra.
"""

import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().with_name("LumenFarm.pyw")), run_name="__main__")

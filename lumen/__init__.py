"""Lumen Farm: autofarming propio para 7DS Grand Cross."""

__version__ = "0.37.3-alpha"


def _yaml_rapido():
    """Lector de YAML en C (libyaml) si esta instalado: el de Python puro tardaba ~1,2 s del arranque (2026-11-13).
    Lee lo mismo que yaml.safe_load; si no esta, todo sigue igual."""
    try:
        import yaml

        if getattr(yaml, "__with_libyaml__", False) and not getattr(yaml.safe_load, "_rapido", False):
            def safe_load(stream):
                return yaml.load(stream, Loader=yaml.CSafeLoader)

            safe_load._rapido = True
            yaml.safe_load = safe_load
    except Exception:
        pass


_yaml_rapido()


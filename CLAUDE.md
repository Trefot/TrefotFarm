# Lumen Farm

Bot de autofarming para 7DS Grand Cross (Python 3.12, PyQt5, Windows). Textos y nombres en español.
Leer LEEME.txt para la estructura.

## Versiones

Reglas completas en CAMBIOS.txt. Resumen:
- Formato `MAYOR.NOVEDAD.ARREGLO-etapa` (ahora `0.x.y-alpha`). La versión está en `lumen/__init__.py`
  y, mientras exista, también en `trefot/__init__.py` (tiene que ser la misma).
- Se sube una vez por PR, según lo más grande que traiga: novedad (algo nuevo que se nota) sube el
  segundo número; arreglos, textos, retoques y datos suben el tercero. La 1.0.0 es solo el lanzamiento.
- En cada PR, añadir arriba de "CAMBIOS" en CAMBIOS.txt la versión nueva con sus cambios en pocas líneas.

## Pruebas

`python3 -m unittest discover -s pruebas -t pruebas` (en Windows, Probar.bat). Tienen que pasar antes de subir.

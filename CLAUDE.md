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

## Trabajo a medias

- **Metas de material** (diseño aprobado por el usuario): datos, lógica (`lumen/metas.py`) y diálogos
  (`lumen/gui/metas.py`) están en el commit 944477b, deshecho en 487831b para sacar antes un arreglo.
  Para seguir: `git revert 487831b`. Falta: botón "Metas x/y" y progreso en "Puedes conseguir" de Inicio,
  chip "Meta" en la barra de Empezar (parar al cumplirla; en el plan, saltar a la siguiente tarea),
  quitar la línea "Hoy", y pruebas. 36 materiales tienen ficha de galería en premios.yaml y se cuentan
  solos; esencia negra, piedra del despertar, cartas y escenas no (se ajustan a mano).
- **Probar con el juego**: la prueba rápida (Farmear → Plan) aún no ha pasado entera. En la prueba de
  la 0.2.1 (Perros Floor 1-3) el bot creía estar en los pisos sin haber entrado a la bestia (contaba
  "Obtain Floor N First Clear Reward") y no veía el Floor 1 (el OCR lee "Floor I"): arreglado en 0.2.2
  con capturas reales; con la 0.2.2 ganó Floor 1, 2 y 3 seguidos. 0.2.3: objetivo de los lobos por
  fase, pantallas sin imagen tras ganar, Indura acepta como AutoFarming y foto del botín. 0.2.4 abre el
  piso por su círculo: ganó F1-F3 en ~2,5 min. 0.2.5 (sin probar): fase 3 solo áreas/ultis, Reset tras el F3,
  cartas que no entran = bloqueadas. 0.2.7: cantidades del botín con dígitos reales
  (assets/digitos_juego.npz: unidades 0, 2, 3, 4, 5 y decena 1). FALTAN 6-9 y decenas 2-9: las casillas
  que no reconoce se guardan en recompensas/digitos_nuevos para añadirlas. 0.3.0: botín unido a las tablas de premios
  (premios.yaml lleva `galeria:`; recompensas.vincular_premios). PENDIENTE: el perro claro (der) nunca se
  confirma al apuntar.
  0.2.6 (sin probar): avisos de sesión cerrada (el juego cerró la sesión tras 1 h de Indura y el bot se
  quedó 6 min sin reconocer nada) y cartas de Indura que no entran. El bot NO escribe la contraseña. El juego no acepta clics de un proceso sin
  permisos de administrador: las pruebas en vivo las lanza el usuario desde Lumen.

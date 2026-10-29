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

- **Floor 4 del ciervo con guion** (0.4.2): el motor `lumen/guiones.py` (EstrategiaGuion, misma forma
  que la Estrategia de perros_piso4) y el guion `lumen/datos/guiones/ciervo_piso4.yaml` estan hechos y
  probados con manos simuladas (pruebas/test_guiones.py). Falta el modo: navegar al Floor 4 de
  Eikthyrnir, detectar sus 4 fases (capturas de F3 y F4), un Equipo con freyja_roja,
  thor_the_god_of_thunder_azul, sun_god_freyr_rojo (es LR en el juego) y god_of_war_tyr_verde, y las
  capturas de sus cartas. Los orbes de la ulti se cuentan, no se leen de pantalla.

- **Metas de material** (diseño aprobado por el usuario): datos, lógica (`lumen/metas.py`) y diálogos
  (`lumen/gui/metas.py`) están en el commit 944477b, deshecho en 487831b para sacar antes un arreglo.
  Para seguir: `git revert 487831b` (choca con la 0.3.0, que ya puso `galeria:` en premios.yaml:
  quedarse con lo de la 0.3.0). Falta: botón "Metas x/y" y progreso en "Puedes conseguir" de Inicio,
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
  (premios.yaml lleva `galeria:`; recompensas.vincular_premios). 0.3.1 (sin probar): cartas bloqueadas por el velo
  oscuro, Restart y volver a abrir el juego (Run Game). 0.4.0: probadas F1-3 de Hraesvelgr, Eikthyrnir
  (3 de 3, ~2,6 min) y Nidhoggr; 0.4.1 arregla pisos superados y turnos falsos por el talento de Odin.
  Sin probar: Ratatoskr, 5 demonios (molde en
  modos/indura.py, pestanas por el icono de AutoFarming) y Fuerte Solgres (modos/fuerte_solgres.py).
  PENDIENTE: el perro claro (der) nunca se confirma al apuntar.
  0.2.6 (sin probar): avisos de sesión cerrada (el juego cerró la sesión tras 1 h de Indura y el bot se
  quedó 6 min sin reconocer nada) y cartas de Indura que no entran. El bot NO escribe la contraseña. El juego no acepta clics de un proceso sin
  permisos de administrador: las pruebas en vivo las lanza el usuario desde Lumen.

# Lumen Farm

Bot de farmeo para 7DS Grand Cross (Python 3.12, PyQt5, Windows). Textos y nombres en español.
Leer LEEME.txt para la estructura.

## Versiones

Reglas completas en CAMBIOS.txt. Resumen:
- Formato `MAYOR.NOVEDAD.ARREGLO-etapa` (ahora `0.x.y-alpha`). La versión está en `lumen/__init__.py`.
- Se sube una vez por PR, según lo más grande que traiga: novedad (algo nuevo que se nota) sube el
  segundo número; arreglos, textos, retoques y datos suben el tercero. La 1.0.0 es solo el lanzamiento.
- En cada PR, añadir arriba de "CAMBIOS" en CAMBIOS.txt la versión nueva con sus cambios en pocas líneas.

## Pruebas

`python3 -m unittest discover -s pruebas -t pruebas` (en Windows, Probar.bat). Tienen que pasar antes de subir.

## La IA del bot

El plan completo esta en `IA.md` (leer, decidir, aprender solo y equipos que el bot propone y prueba).
Al terminar una pieza, actualizar su estado alli. En el PC: `py -m lumen.ia.efectos` dice cuanto entiende
el lector de los textos de cartas capturados y que frases faltan (anadirlas con su prueba real).

## Estado (revisión del 2026-11-23, 0.42.2)

- Modos: bestias Floor 1-3 (pájaro, ciervo, perros, serpiente), Floor 4 de pájaro, ciervo y perros, los 5 demonios
  e Indura, y Fuerte Solgres (oro y monedas SA). El historial detallado de cada versión está en CAMBIOS.txt.
- Floor 4 de pájaro y ciervo (`lumen/modos/bestias_piso4.py`): reglas propias por fase (0.41.0) y fase también por el
  color de la barra del jefe (`lumen/vida_jefe.py`, 0.41.5). Pájaro F4 probado: 9 de 9 victorias (2026-11-13).
- Metas de material, plan del día con "🎯 Meta", prueba rápida, diario de peleas y aprender solo: en el código y con
  pruebas; el plan de la IA y el estado de cada pieza, en `IA.md`.
- Pendiente visto en pruebas reales: un objeto del botín del pájaro F4 sin nombre ("Sin nombre (48)").

## Notas para trabajar

- El usuario NO quiere ventanas nuevas: todo va integrado en las páginas que ya existen.
- Las pruebas en vivo las lanza el usuario desde Lumen: el juego no acepta clics de un proceso sin permisos de
  administrador. El bot NO escribe la contraseña.
- Las órdenes del móvil van por ntfy; la app de iPhone no deja escribir mensajes (se usa ntfy.sh en Safari o Atajos).

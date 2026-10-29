# La IA de Lumen Farm

Objetivo (palabras del usuario): que el bot **aprenda a jugar**, **lea las pasivas** de personajes y
enemigos, **analice qué conviene lanzar**, y a futuro **proponga equipos, los pruebe, descarte los que
no funcionan y recomiende el mejor**, mejorándolos solo cuando salgan héroes nuevos. Así las
actualizaciones del juego cuestan menos.

Este archivo es el plan común. Cada pieza se puede usar por sí sola y el bot juega mejor con cada una.
Al terminar una pieza, actualizar su estado aquí.

## Lo que NO se hace (y por qué)

Aprender desde cero a base de prueba y error (como una IA de ajedrez) necesitaría decenas de miles de
peleas reales: meses, mucha estamina, muchas derrotas y riesgo de baneo, y no hay simulador del juego.
La IA de Lumen **parte de saber leer y de lo que el jugador le enseña**, y desde ahí **mejora sola con
sus propias peleas**, probando variantes de vez en cuando y siempre dentro de jugadas razonables.

## Las piezas

| # | Pieza | Qué hace | Estado |
|---|---|---|---|
| 1 | **Lector de efectos** (`lumen/ia/efectos.py`) | Texto de una habilidad o de un patrón de jefe (inglés, el del cliente de PC) → efectos y mecánicas que el bot entiende: daño 220 % a uno, baja ataque 20 % 1 turno, quita postura, cura, limpia… y para jefes: Inmortalidad, Torrent, reducción de daño por atributo… con su **contramedida**. Con las 1.083 cartas capturadas entiende el 97,5 % de las frases (0.8.2): glosario del juego (*Pierce, *Bleed, *Taunt...), danos por turno, quitar buffs/orbes/rangos, bloqueos, posturas, inmunidad... y los fallos del lector de texto ("for I turn(s)", el % fuera de sitio). | **Cartas hecho (0.8.2)**; faltan pasivas y reliquias (pieza 2) |
| 2 | **Lectura en el juego** | La captura de héroes ya guarda el texto de cada carta (`capturas/heroes/catalogo.yaml`). Falta: pasiva, talento, unidad y gracia de cada héroe, sus **reliquias** (ver abajo), y la "Enemy Info" de cada jefe (Basic Info, Phase 1-4: Pattern Description e iconos de Unique Info). | Pendiente (PC) |
| 3 | **Estado en vivo** | Reconocer en la pelea los iconos que importan: Inmortalidad (y cuántas), Evasión, postura, Torrent, bloqueo de habilidades, fase, orbes de la ulti. AutoFarming ya tiene imágenes de varios (`immortality.png`, `evasion.png`, `stance_active.png`, `block_skill_debuff.png`). | Pendiente (PC) |
| 4 | **Decidir** | El juego inteligente (`lumen/inteligencia.py`) puntúa cada jugada; con 1-3 la puntuación suma lo que pide el jefe ahora (si tiene postura, valen más las cartas que la quitan; con Inmortalidad, las de varios golpes; si el patrón pide un color, ese color). Los guiones (`lumen/guiones.py`) quedan para reglas exactas que dicte el jugador. Hecho: `lumen/ia/decidir.py` (pesos por mecánica y motivo de cada ajuste), `lumen/datos/jefes.yaml` (Enemy Info por fase; ya está el ciervo F4) y `Jugador.mecanicas` en el juego inteligente. Falta que cada modo ponga las mecánicas de su fase (`decidir.mecanicas_de(destino, fase)`). | **Base hecha (0.7.0)** |
| 5 | **Diario de peleas** | Cada decisión con su contexto (fase, turno, mano, estado del jefe) y cómo acabó la pelea (victoria, tiempo, fase de la derrota). "Aprender de mí" ya graba las peleas del jugador así. Hecho: `lumen/ia/diario.py` en el modo de las bestias (Floor 1-3 y Floor 4): `logs/diario/<destino>.jsonl`, `resumen()` y `texto()`; la orden **diario** del móvil manda el resumen para pasárselo al analista. Falta: Indura y los demonios, y el estado del jefe cuando exista la pieza 3. | **Hecho en bestias (0.7.0)** |
| 6 | **Aprender solo** | Con el diario: casi siempre juega lo que mejor ha ido; de vez en cuando (p. ej. 1 de cada 10 peleas) prueba una variante razonable. Si gana más rápido, la adopta; si pierde, la descarta. Por jefe y equipo. Hecho: `lumen/ia/aprendizaje.py` ajusta 3 parámetros del juego inteligente (guardar para el turno siguiente, valor de la ulti, cartas de un objetivo en fases de área) en las bestias Floor 1-3; opción "Aprender solo". Siguiente: los pesos de `decidir` cuando un modo use mecánicas, y por equipo. | **Hecho en bestias F1-3 (0.7.0)** |
| 7 | **Equipos** | Propone equipos con los héroes **y reliquias** que tiene el jugador (por lo que hacen sus cartas, pasivas y reliquias frente a las mecánicas del jefe), los prueba unas peleas, descarta los que fallan, deja los que funcionan como opción y el más rápido como recomendado (ya existe la medición: `equipos.mas_rapido`). Con un héroe o una reliquia nuevos, los lee (pieza 2) y los prueba en los equipos donde encajen. | Pendiente |
| 8 | **Analista (opcional)** | Claude por API (necesita clave y tiene coste): lee la Enemy Info de un jefe nuevo y propone un guion inicial; revisa el diario y sugiere cambios. El bot sigue jugando local, sin internet en cada turno. Coste estimado (precios de 2026-10): unos céntimos por consulta; de 1 a 20 USD al mes según el modelo y cuántas veces se use. Mientras tanto, el analista puede ser Claude en estas sesiones (se le pasan capturas y el diario). | Idea |

## Reliquias (Holy Relics)

Una reliquia cambia cómo rinde un héroe: sube sus stats y a veces le da un efecto propio (como una
pasiva más). **Un héroe puede tener más de una reliquia distinta** (ya hay un personaje con 2), así que
"tener el héroe" no basta: el equipo puede necesitar una reliquia concreta. Caso real (2026-10-29):
**Freyja tiene 2 reliquias** (sus textos, pendientes de captura: el juego estaba en mantenimiento).

- **Base del bot:** cada personaje lleva sus reliquias posibles (`reliquias:` en personajes.yaml, ver
  Formatos) con su nombre y el texto de su efecto; el lector de efectos (pieza 1) lo entiende igual que
  una pasiva.
- **El jugador marca qué reliquias tiene** (igual que marca los héroes que tiene, en Personajes).
- **Equipos:** cada equipo dice qué reliquia lleva cada héroe, si la necesita (`reliquias:` en
  equipos.yaml). Inicio y Farmear lo muestran junto al retrato ("con reliquia X") y "te falta" cuenta
  también las reliquias. Hoy solo está como texto en las notas de algunos equipos ("Freyja con reliquia").
- **Medición:** el mismo equipo con otra reliquia cuenta como otro equipo (puede ganar más o menos rápido).
- **Equipos que propone el bot (pieza 7):** solo con las reliquias que tiene el jugador; si una reliquia
  que no tiene haría mucho mejor un equipo, lo dice como sugerencia.

## Formatos

- **Efecto** (de una carta, pasiva...): `tipo` (dano, debuff, buff, quitar_postura, curar, limpiar,
  escudo, aturdir, amplificar, orbes, ignora_evasion...), `valor` (en %), `objetivo` (uno, todos,
  aliados, aliado, si_mismo), `turnos`, `detalle` (p. ej. el stat: "attack").
- **Mecánica** (de un jefe): `tipo` (inmortalidad, evasion, postura, torrent, reduccion_dano_atributo,
  curacion_jefe, proteccion, bloqueo...), `detalle` y `contra`: lo que la vence (efectos o acciones:
  "ulti", "mismo_atributo", "secuencia_atributos", "quitar_postura", "limpiar"...).
- **Reliquia** (en personajes.yaml, dentro de su héroe): `reliquias: [{id, nombre, efecto}]`, donde
  `efecto` es el texto del juego. En equipos.yaml, opcional por equipo: `reliquias: {heroe: id_reliquia}`
  (o `true` si ese héroe solo tiene una).
- Lo que el lector no entiende se lista (`efectos.no_entendido`) para ir ampliándolo con textos reales.

## Fuentes de texto reales

- Skill Info de cada carta (captura de héroes, PC). Ejemplo: Raining Blades de Freyr.
- Enemy Info de cada jefe (fases y pasivas del piso). Ejemplo: Eikthyrnir Floor 4, en
  `pruebas/test_efectos.py`.

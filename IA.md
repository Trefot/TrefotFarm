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
| 1 | **Lector de efectos** (`lumen/ia/efectos.py`) | Texto de una habilidad o de un patrón de jefe (inglés, el del cliente de PC) → efectos y mecánicas que el bot entiende: daño 220 % a uno, baja ataque 20 % 1 turno, quita postura, cura, limpia… y para jefes: Inmortalidad, Torrent, reducción de daño por atributo… con su **contramedida**. | **Empezado (0.6.1)** |
| 2 | **Lectura en el juego** | La captura de héroes ya guarda el texto de cada carta (`capturas/heroes/catalogo.yaml`). Falta: pasiva, talento, unidad y gracia de cada héroe, y la "Enemy Info" de cada jefe (Basic Info, Phase 1-4: Pattern Description e iconos de Unique Info). | Pendiente (PC) |
| 3 | **Estado en vivo** | Reconocer en la pelea los iconos que importan: Inmortalidad (y cuántas), Evasión, postura, Torrent, bloqueo de habilidades, fase, orbes de la ulti. AutoFarming ya tiene imágenes de varios (`immortality.png`, `evasion.png`, `stance_active.png`, `block_skill_debuff.png`). | Pendiente (PC) |
| 4 | **Decidir** | El juego inteligente (`lumen/inteligencia.py`) puntúa cada jugada; con 1-3 la puntuación suma lo que pide el jefe ahora (si tiene postura, valen más las cartas que la quitan; con Inmortalidad, las de varios golpes; si el patrón pide un color, ese color). Los guiones (`lumen/guiones.py`) quedan para reglas exactas que dicte el jugador. | Pendiente |
| 5 | **Diario de peleas** | Cada decisión con su contexto (fase, turno, mano, estado del jefe) y cómo acabó la pelea (victoria, tiempo, fase de la derrota). "Aprender de mí" ya graba las peleas del jugador así. | Parcial |
| 6 | **Aprender solo** | Con el diario: casi siempre juega lo que mejor ha ido; de vez en cuando (p. ej. 1 de cada 10 peleas) prueba una variante razonable. Si gana más rápido, la adopta; si pierde, la descarta. Por jefe y equipo. | Pendiente |
| 7 | **Equipos** | Propone equipos con los héroes que tiene el jugador (por lo que hacen sus cartas y pasivas frente a las mecánicas del jefe), los prueba unas peleas, descarta los que fallan, deja los que funcionan como opción y el más rápido como recomendado (ya existe la medición: `equipos.mas_rapido`). Con un héroe nuevo, lo lee (pieza 2) y lo prueba en los equipos donde encaje. | Pendiente |
| 8 | **Analista (opcional)** | Claude por API (necesita clave y tiene coste): lee la Enemy Info de un jefe nuevo y propone un guion inicial; revisa el diario y sugiere cambios. El bot sigue jugando local, sin internet en cada turno. | Idea |

## Formatos

- **Efecto** (de una carta, pasiva...): `tipo` (dano, debuff, buff, quitar_postura, curar, limpiar,
  escudo, aturdir, amplificar, orbes, ignora_evasion...), `valor` (en %), `objetivo` (uno, todos,
  aliados, aliado, si_mismo), `turnos`, `detalle` (p. ej. el stat: "attack").
- **Mecánica** (de un jefe): `tipo` (inmortalidad, evasion, postura, torrent, reduccion_dano_atributo,
  curacion_jefe, proteccion, bloqueo...), `detalle` y `contra`: lo que la vence (efectos o acciones:
  "ulti", "mismo_atributo", "secuencia_atributos", "quitar_postura", "limpiar"...).
- Lo que el lector no entiende se lista (`efectos.no_entendido`) para ir ampliándolo con textos reales.

## Fuentes de texto reales

- Skill Info de cada carta (captura de héroes, PC). Ejemplo: Raining Blades de Freyr.
- Enemy Info de cada jefe (fases y pasivas del piso). Ejemplo: Eikthyrnir Floor 4, en
  `pruebas/test_efectos.py`.

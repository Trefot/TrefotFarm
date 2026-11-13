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
| 1 | **Lector de efectos** (`lumen/ia/efectos.py`) | Texto de una habilidad o de un patrón de jefe (inglés, el del cliente de PC) → efectos y mecánicas que el bot entiende: daño 220 % a uno, baja ataque 20 % 1 turno, quita postura, cura, limpia… y para jefes: Inmortalidad, Torrent, reducción de daño por atributo… con su **contramedida**. Con las 1.083 cartas capturadas entiende el 97,5 % de las frases (0.8.2): glosario del juego (*Pierce, *Bleed, *Taunt...), danos por turno, quitar buffs/orbes/rangos, bloqueos, posturas, inmunidad... y los fallos del lector de texto ("for I turn(s)", el % fuera de sitio). | **Hecho (0.9.7)**: cartas 97,9 %, pasivas/gracias/talentos/mandamientos/reliquias 90 % |
| 2 | **Lectura en el juego** | Desde la 0.19.0 los textos de las cartas vienen de 7dshub (`lumen/datos/habilidades.yaml`) y la captura de héroes y de pasivas se quitó en la 0.20.0 (7dshub tiene pasivas, talentos, unidades y reliquias para sacarlas cuando hagan falta). Falta: pasiva, talento, unidad y gracia de cada héroe, sus **reliquias** (ver abajo), y la "Enemy Info" de cada jefe (Basic Info, Phase 1-4: Pattern Description e iconos de Unique Info). | Pendiente (PC) |
| 3 | **Estado en vivo** | Reconocer en la pelea los iconos que importan: Inmortalidad (y cuántas), Evasión, postura, Torrent, bloqueo de habilidades, fase, orbes de la ulti. AutoFarming ya tiene imágenes de varios (`immortality.png`, `evasion.png`, `stance_active.png`, `block_skill_debuff.png`). | Pendiente (PC) |
| 4 | **Decidir** | El juego inteligente (`lumen/inteligencia.py`) puntúa cada jugada; con 1-3 la puntuación suma lo que pide el jefe ahora (si tiene postura, valen más las cartas que la quitan; con Inmortalidad, las de varios golpes; si el patrón pide un color, ese color). Los guiones (`lumen/guiones.py`) quedan para reglas exactas que dicte el jugador. Hecho: `lumen/ia/decidir.py` (pesos por mecánica y motivo de cada ajuste), `lumen/datos/jefes.yaml` (Enemy Info por fase; ya está el ciervo F4) y `Jugador.mecanicas` en el juego inteligente. Desde la 0.19.0 las bestias Floor 1-3 (Inteligente) ponen las de su piso y fase (`<bestia>_f<piso>`), con los jefes de 7dshub en `jefes.yaml` y los textos de las cartas en `habilidades.yaml`. Desde la 0.21.0 el planificador tambien busca objetivos de turno (`inteligencia.objetivos_de`: N cartas del mismo rango, mismo color seguido). Falta: Floor 4 e Indura. | **Base hecha (0.7.0)** |
| 5 | **Diario de peleas** | Cada decisión con su contexto (fase, turno, mano, estado del jefe) y cómo acabó la pelea (victoria, tiempo, fase de la derrota). "Aprender de mí" ya graba las peleas del jugador así. Hecho: `lumen/ia/diario.py` en el modo de las bestias (Floor 1-3 y Floor 4): `logs/diario/<destino>.jsonl`, `resumen()` y `texto()`; la orden **diario** del móvil manda el resumen para pasárselo al analista. En los demonios en tiempo real desde la 0.14.0 (`indura.py`, con nivel y forma de jugar). Falta: el estado del jefe cuando exista la pieza 3. | **Hecho en bestias (0.7.0)** |
| 6 | **Aprender solo** | Con el diario: casi siempre juega lo que mejor ha ido; de vez en cuando (p. ej. 1 de cada 10 peleas) prueba una variante razonable. Si gana más rápido, la adopta; si pierde, la descarta. Por jefe y equipo. Hecho: `lumen/ia/aprendizaje.py` ajusta 3 parámetros del juego inteligente (guardar para el turno siguiente, valor de la ulti, cartas de un objetivo en fases de área) en las bestias Floor 1-3 y Floor 4, y en los demonios jugando "Inteligente" (0.14.0, por nivel); opción "Aprender solo". Siguiente: los pesos de `decidir` cuando un modo use mecánicas, y por equipo. | **Hecho en bestias F1-3 (0.7.0)** |
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

## 2026-11-09: aprender de cada pelea y entender pasivas

- Paso 5 ampliado: `lumen/ia/lecciones.py` aprende de UNA pelea (victoria rapida refuerza; derrota castiga lo de los ultimos turnos de esa fase; por tardar, mas area y ultis). Se aplica en `Jugador.elegir` por destino y fase.
- Paso 1: `lumen/ia/pasivas.py` lee la pasiva unica (dano propio, por tipo de ataque, ulti) y contra que jefe aplica.
- Reglas que ensena el jugador: `lumen/modos/rata.py` (Ratatoskr), a convertir en un formato por jefe (paso 3).
- 0.29.0: conocimiento por jefe en `lumen/datos/conocimiento.yaml` (`lumen/ia/conocimiento.py`): por destino y fase, `preferir` (x1,6) y `evitar` (x0,3) un tipo de carta; se aplica en `Jugador.elegir` tras las pasivas. Lo que necesita mirar la pantalla (troncos de la rata) sigue en `rata.py`.
- 0.29.0: lo aprendido se ve en la pestana "Aprendido" y en la orden "diario" (`lecciones.texto_modo`). Talentos: se usan cada vez que se recargan (cooldown y limite leidos del texto del talento).

## 0.31.2: correcciones de estabilidad del aprendizaje

El reconocimiento generico identifica las ultis sin permitir fusionarlas. Los demonios registran cambios de turno
observados en las casillas libres. Las lecciones omiten diarios antiguos con turnos desconocidos para evitar
castigar toda una pelea como si fuera un turno. Falta confirmar la deteccion de turnos con capturas del juego.

## 0.32.0: primer reproductor de capturas

Laboratorio (con llave de administrador) abre una secuencia de imagenes de ventana de 550x940. El lector real de mano y la IA general
proponen una accion y la dibujan, sin ejecutar entradas ni escribir diarios. Cada captura se analiza desde cero;
no reconstruye acciones previas ni ejecuta los guiones de cada modo. Piso/fase/acciones son controles explicitos.
Siguiente: casos con secuencias reales del juego y comparacion entre estrategias/versiones.

## 0.32.0: propuestas y confirmaciones

El diario de bestias y demonios distingue propuestas, confirmaciones por bajada de casillas y acciones
no confirmadas. Las lecciones y el resumen de cartas ganadoras omiten propuestas e intentos sin confirmar.
La confirmacion es evidencia visual de consumo de casilla, no una lectura exacta del dano o del resultado
de esa carta. Los registros historicos conservan su compatibilidad; no se reescriben lecciones antiguas.
El reproductor queda en Laboratorio, oculto sin llave y con comprobacion de permisos en el backend.

## 0.33.0: memoria aislada, comparacion y recuperacion

`ia/perfiles.py` separa lecciones y estadisticas por destino (incluye piso/nivel), equipo completo y huella de
los YAML de conocimiento. Los modos reales no aplican la memoria global historica. Sin equipo identificado
no exploran variantes ni reutilizan lecciones; el juego general y los guiones siguen disponibles. Las
estadisticas nuevas requieren acciones confirmadas y conocimiento compatible. Exploracion tras 5 partidas
de base; adopcion exige mejora de victorias/h sin bajar la tasa de victoria.

Laboratorio compara base y aprendida con la misma captura. Incluye copias y restauracion de lecciones y
parametros con autorizacion administrativa, corte de estadisticas anteriores y copia previa. Si una escritura
interrumpe la restauracion, el perfil queda suspendido hasta recuperarlo. Un equipo distinto no comparte memoria.

Conocimiento 7DS muestra el inventario y huecos de reconocimiento. Los destinos de pajaro/ciervo F4 se unifican
con jefes.yaml. Esto no completa el estado vivo de buffs/vida/orbes ni aporta un simulador, nuevos guiones
validados ni equipos probados automaticamente. Esos pasos siguen pendientes de capturas y partidas reales.

## 0.34.0: observacion y evaluacion de resultados

`ia/estado.py` detecta iconos conocidos en una zona superior que excluye las cartas y registra coincidencia
y posicion. Vida, orbes y postura se mantienen desconocidos. Ajustes solo para evasion del pajaro F4/fase4
y bloqueo del pajaro F4/fase1; otros contextos registran evidencia sin deducir contramedidas. No elimina
reglas de fase por no ver un icono. Falta calibracion con capturas reales de combate.

`ia/evaluacion.py` evalua diarios sin importarlos a la memoria: separa version/origen/configuracion, informa
acciones sin confirmar, fallos por fase, partidas/h e intervalo orientativo de tasa. El origen se declara
en el diario; no se certifica como real a partir del archivo. `ia/equipos.py` ordena equipos registrados
por disponibilidad, compatibilidad y medidas comparables de la version actual; no crea ni ejecuta equipos
nuevos. Laboratorio incluye estas operaciones con la llave administrativa.

## Correccion de guiones y ritmo (0.36.5-alpha)

- El historial del guion se identifica por fase, turno y posicion de accion: repetir un toque no suma otra carta y mover no desplaza la secuencia de atributos.
- En ciervo F4 fase 2, si un movimiento no puede ejecutarse, no se reemplaza por un ataque de la IA general. Se usan destinos ocupados y se espera otra lectura si no hay dos cartas.
- Contraste con AutoFarming: `scripts/utilities/deer_floor4_fighting_strategies.py` en `6c78e5564bc0568ab54fc6b8c96afc7abae8e08b` (MIT). Su fase 2 contempla tres cartas y un movimiento; eso no demuestra por si solo la causa de la derrota reportada.
- Pausa de 0,25 s solo tras una normal confirmada sin fusiones. Los otros margenes no cambian.
- La firma de perfiles incluye ambos motores F4 para no mezclar memoria entre versiones del guion.
- Pendiente: equipo exacto y registro/captura del turno de la derrota real de F2; no se ha validado una victoria en el juego en esta revision.

# Integrar TrefotFarm en otro bot

Guía para reutilizar las piezas de TrefotFarm (7DS Grand Cross, cliente de PC Global) dentro de
otro bot. Todo el código está en `trefot/`; la interfaz (`trefot/gui/`) es opcional.

> Probado: Skollandhati & Hati · Floor 4 con Odin, Gawain, Freyja (Strength) y Thonar (Speed):
> **5 de 5 victorias seguidas, ~2,5 min por pelea, sin reinicios**.

## 1. Requisitos

- Windows, Python 3.12 (`requirements.txt`). `scikit-learn==1.5.1` es obligatorio: el modelo
  `assets/modelos/ground_cards_predictor.svc` está guardado con esa versión (con `dill`).
- El juego corre **como administrador**: el proceso del bot también tiene que serlo, si no
  Windows bloquea mover la ventana y los clics (`SetWindowPos` da "Acceso denegado").
- Ventana del juego en **554x960 contando la barra de título y los bordes** (`ventana.TAMANO_OBJETIVO`).
  Da capturas de 550x940; todas las plantillas y coordenadas están medidas a ese tamaño. Con el
  área interior a 540x960 el reconocimiento baja mucho (0.76 → 0.58).

## 2. Mapa del código

| Módulo | Qué hace | ¿Depende del resto? |
|---|---|---|
| `ventana.py` | Encontrar/ajustar/capturar la ventana `7DS` (BitBlt del escritorio). | `config` |
| `entrada.py` | Clics y arrastres con el ratón real. | `control` |
| `vision.py` | `Plantilla`: template matching (TM_CCOEFF_NORMED) con varias imágenes por plantilla. | no |
| `juego.py` | Todas las plantillas de pantalla y coordenadas fijas del juego. | `vision` |
| `cartas.py` | Leer la mano: 8 cartas, tipo (normal/ulti/bloqueada/hueco), rango, huecos libres. | `juego` |
| `personajes.py` | Base de personajes: fichas (`datos/personajes.yaml`) e imágenes (`assets/personajes`). | `vision` |
| `equipo.py` | Reconocer qué carta es cada una (Odin single, etc.) y comprobar el equipo por retratos. | `personajes` |
| `motor.py` | Máquina de estados genérica (un estado = una función), vigilante de atascos. | varios |
| `modos/perros_piso4.py` | El modo completo: navegación + pelea + **estrategia pura** (`Estrategia`). | todo |
| `botin.py` / `recompensas.py` | Leer la pantalla de Victory: objetos, cantidades y oro. | `vision` |
| `actualizador.py` | Actualizaciones obligatorias desde GitHub. **No lo uses** si lo metes en tu bot. | git |

Lo más fácil de reutilizar sin el resto:

- **`Estrategia`** (en `modos/perros_piso4.py`): no toca la pantalla. Recibe la fase, el turno, la
  acción y la mano ya etiquetada, y devuelve `(índice_de_carta | (origen, destino), objetivo, usar_talento)`
  o lanza `Reiniciar(motivo)`. Puedes conectarla a tu propio lector de mano y a tus clics.
- **`cartas.py` + `equipo.py`**: lectura de la mano con nombres de carta, a partir de las imágenes de
  `assets/personajes`.

## 3. El guion de Perros Floor 4

Siempre se selecciona el perro **que NO está en la burbuja** (la burbuja es su Stance y no se puede
seleccionar): el derecho en la fase 1 y el lobo azul izquierdo en la fase 2.

| Fase / turno | Acciones (en orden) |
|---|---|
| F1 T1 | postura de Thonar · otra de Thonar · 2 normales de Freyja |
| F1 T2 | Talent de Odin + Freyja (si su ulti no está) o la otra de Thonar · single de Gawain · relleno (nunca Odin) · **single de Odin siempre como 4.ª** |
| F2 T1 | quitar Stance: postura de Thonar → single de Odin → área de Gawain (la primera **no bloqueada**) · área de Gawain u Odin · ulti de Freyja · área de Odin |
| F3 T1 | **no se juega ninguna carta**: solo se mueven cartas (arrastrar una sobre la de su izquierda); el golpe extra de la ulti de Freyja termina la pelea |

Si una fase dura más turnos (F1 > 2, F2 > 1, F3 > 1) o falta una carta clave, se rinde
(Pausa → Forfeit → OK) y se repite.

## 4. Valores medidos con el juego real (lo que más costó)

| Qué | Valor | Dónde |
|---|---|---|
| Duración del clic | ~120 ms (con 30–70 ms el juego ignora clics de cartas y perros) | `entrada.DURACION_CLIC` |
| Pausa entre cartas | esperar a que la carta ocupe su hueco + 0,5 s; **comprobar también la última** | `perros_piso4._jugar_turno` |
| Carta bloqueada | se ve **oscurecida**: brillo medio del interior < 90 (bloqueadas 73–83, normales 96+) | `cartas.BRILLO_BLOQUEADA` |
| Tipo de carta | el modelo de tipos de AutoFarming ya no sirve (dice "ulti" a todo); ulti = sin estrellas de rango | `cartas.tipo_de` / `rango_de` |
| Carta desde la ficha del héroe | fila "Skills" en (35,600)-(89,698), (95,…), (160,…); reescalar ×1,22 ancho ×1,26 alto; umbral 0,55 | `juego.FICHA_CARTAS`, `personajes.ESCALA_FICHA` |
| Carta capturada en pelea | interior sin marco (15 % lados, 20 % arriba/abajo); umbral 0,70 | `equipo.recorte_para_plantilla` |
| Retratos (pantalla del equipo) | caras en x = 72,178,285,391 (+22..+80), y 290–390; umbral 0,6 | `juego.RETRATOS` |
| Perros | izquierdo (160,412), derecho (346,386); talent (276,665) | `juego.COORD` |
| Botín (Victory) | casillas cada 81 px desde x=85; filas y=405 (1), 362/449 (2), 319/406/493 (3); oro en (85,540)-(175,572) | `botin.py` |

Las coordenadas son relativas a la esquina superior izquierda de la **ventana** (no del área interior).

## 5. Base de personajes

- `trefot/datos/personajes.yaml`: ficha de cada personaje (atributo, raza, roles, cartas).
- `assets/personajes/<id>/`: `<carta>_ficha.png` (de la ficha del héroe), `<carta>.png` (de una pelea,
  tiene prioridad), `retrato.png`, `talento.png`.
- `trefot/datos/equipos.yaml`: equipos recomendados por contenido.
- Una carta se nombra `personaje.carta`, p. ej. `odin.single`, `thonar_azul.postura`.

## 6. Créditos y licencia

Las plantillas de `assets/imagenes` y el modelo de `assets/modelos` vienen de
[AutoFarming](https://github.com/PhantomPilots/AutoFarming) (licencia MIT, ver
`LICENSE_AutoFarming_original.txt`); hay que conservar ese aviso. El resto del código es de TrefotFarm.

Usar bots va contra las reglas de Netmarble y puede costar un baneo.

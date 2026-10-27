"""Todo lo que el bot sabe del juego: plantillas de pantalla y coordenadas fijas.

Las coordenadas son para la ventana de 554x960 (boton "Ajustar ventana") y son relativas
a la esquina superior izquierda de la ventana. Las plantillas vienen del proyecto AutoFarming
(licencia MIT) y viven en assets/imagenes.
"""

from lumen.vision import Plantilla

P = Plantilla

# ------------------------------------------------------------------- generales
cancelar = P("cancel.png")
menu_batalla = P("battle_menu.jpg")
empezar = P("start.png")
saltar = P("skip.png", "demonic_beasts/skip_masked.png", nombre="saltar")
usar_pocion = P("stamuse.png", nombre="usar_pocion")
pocion_stamina = P("stamina_pot.png")
reconectar = P("reconnect.png")
reiniciar_juego = P("restart.png")
cerrar = P("close.png")
pausa = P("pause.png")
rendirse = P("forfeit.png")
mano_bloqueada = P("skill_locked.png")
carga_taberna = P("tavern_loading_screen.png")
info_mision = P("dailies/quest_info.png")
ok = P(
    "ok_buttons/ok_button.jpg",
    "ok_buttons/OK_save_party.png",
    "ok_buttons/ok_bird_defeat.png",
    "ok_buttons/fb_ok_button.png",
    "ok_buttons/ok_pvp_defeat.png",
    "ok_buttons/salvage_ok.png",
    "ok_buttons/bird_okay.png",
    "ok_buttons/finished_fight_ok.png",
    "ok_buttons/forfeit_fight_ok.png",
    "ok_buttons/demon_ok.jpg",
    "ok_buttons/dead_ok.jpg",
    "ok_buttons/kicked_ok.png",
    "ok_buttons/ok_maintenance.png",
    nombre="ok",
)

# ---------------------------------------------------------- bestias demoniacas
nido_criaturas = P("demonic_beasts/creature_nest.png")
pantalla_bestias = P("demonic_beasts/demonic_beast_battle.png")
carga_bestias = P("demonic_beasts/loading_screen.png")
pajaro = P("demonic_beasts/hraesvelgr.png")
ciervo = P("deer/Eikthyrnir.png")
perros = P("demonic_beasts/skollandhati.png")
serpiente = P("snake/nidhoggr.png")
rata = P("rat/ratatoskr.png")
ORDEN_BESTIAS = (pajaro, ciervo, perros, serpiente, rata)  # orden en el carrusel
piso3_superado = P(
    "demonic_beasts/floor_3_cleared_skollandhati_cleaned.png",
    "demonic_beasts/floor_3_cleared_2_skollandhati.png",
    "demonic_beasts/floor_3_cleared_skollandhati_cleaned_2.png",
    nombre="piso3_superado",
)
extra = P("demonic_beasts/extra.png")
fase_1 = P("demonic_beasts/phase_1.png")
fase_2 = P("demonic_beasts/phase_2.png")
fase_3_perros = P("dogs/phase_3_dogs.png")
victoria = P("demonic_beasts/db_victory.png")
criatura_destruida = P("demonic_beasts/creature_destroyed.png")
derrota = P("demonic_beasts/defeat.png")
mision_semanal = P("demonic_beasts/lazy_weekly_mission.png")
recompensa_garantizada = P("demonic_beasts/guaranteed_reward.png")

# ------------------------------------------------------------------- perros
perro_izq_seleccionado = P("dogs/left_target_sel.png", "dogs/p1targetleft.png", nombre="perro_izq_sel")
perro_der_seleccionado = P("dogs/right_target_sel.png", "dogs/right_target_sel2.png", nombre="perro_der_sel")
espacio_vacio = P(*[f"dogs/empty_slot_{i}.png" for i in range(1, 19)], nombre="espacio_vacio")

# ------------------------------------------------------------------- cartas
rango_bronce = P("bronze_card.png")
rango_plata = P("silver_card.png")
rango_oro = P("gold_card.png")

# --------------------------------------------------------------- coordenadas
COORD = {
    "centro": (270, 480),
    "talento": (276, 665),
    "deslizar_der": (361, 466),
    "deslizar_izq": (177, 463),
    "mision_semanal": (283, 631),
    "perro_izquierdo": (160, 412),  # perro oscuro
    "perro_derecho": (346, 386),  # perro claro
}

# Cara de cada personaje en la pantalla del equipo (antes de Start), de izquierda a derecha.
# Recorte que evita el nivel, los iconos y el asociado de la esquina. Medido con capturas reales.
RETRATOS = [(x + 22, 290, x + 80, 390) for x in (72, 178, 285, 391)]
HOLGURA_RETRATO = 14

# Cartas de la fila "Skills" en la ficha del heroe (Heroes -> personaje): normal 1, normal 2, ulti.
# (x1, y1, x2, y2). Medido en las fichas de Odin y Freyja: el diseno es el mismo para todos.
FICHA_CARTAS = [(35, 600, 89, 698), (95, 600, 149, 698), (160, 600, 214, 698)]  # margen alrededor del recorte al buscar (por si la pantalla se mueve un poco)

REGION = {
    "espacios_cartas": (150, 690, 410, 800),  # (x1, y1, x2, y2) donde se ven los huecos para cartas
    "mano_4": (61, 822, 517, 945),  # las 8 cartas de la mano con 4 unidades
}

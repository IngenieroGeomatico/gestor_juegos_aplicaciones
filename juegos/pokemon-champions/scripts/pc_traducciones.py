"""Tablas de traducción EN → ES y slugs de PokeAPI para Pokémon Champions.

Se separan del script de importación (``importar_datos.py``) para mantenerlo
centrado en la orquestación y facilitar mantener/ampliar las traducciones sin
tocar la lógica de red. La función ``objeto_es`` aplica además la regla de las
mega piedras (``-ite`` → ``-ita``).
"""

from __future__ import annotations

TIPOS_EN_ES = {
    "Normal": "Normal",
    "Fire": "Fuego",
    "Water": "Agua",
    "Electric": "Eléctrico",
    "Grass": "Hierba",
    "Ice": "Hielo",
    "Fighting": "Lucha",
    "Poison": "Veneno",
    "Ground": "Tierra",
    "Flying": "Volador",
    "Psychic": "Psíquico",
    "Bug": "Bicho",
    "Rock": "Roca",
    "Ghost": "Fantasma",
    "Dragon": "Dragón",
    "Dark": "Siniestro",
    "Steel": "Acero",
    "Fairy": "Hada",
}

CATEGORIAS = {"physical": "Físico", "special": "Especial", "status": "Estado"}

STATS_CLAVES = ("hp", "attack", "defense", "sp_attack", "sp_defense", "speed")
STATS_ES = ("ps", "ataque", "defensa", "ataque_esp", "defensa_esp", "velocidad")

EVS_EN_ES = {"HP": "PS", "Atk": "Atq", "Def": "Def", "SpA": "AtqE", "SpD": "DefE", "Spe": "Vel"}

# Nombres mostrados por championsbattledata que necesitan slug distinto en PokeAPI
# o nombre español curado (las formas regionales no tienen entrada directa en
# /pokemon-species/). Clave: mostrar el nombre de la API de cbd, valor: nombre ES.
NOMBRES_FORMAS_ES = {
    "Aegislash Shield Forme": "Aegislash (Forma Escudo)",
    "Alolan Ninetales": "Ninetales de Alola",
    "Alolan Raichu": "Raichu de Alola",
    "Basculegion Female": "Basculegion Hembra",
    "Basculegion Male": "Basculegion Macho",
    "Fan Rotom": "Rotom Ventilador",
    "Florges Red Flower": "Florges (Flor Roja)",
    "Furfrou Natural Form": "Furfrou (Forma Salvaje)",
    "Galarian Slowbro": "Slowbro de Galar",
    "Galarian Slowking": "Slowking de Galar",
    "Galarian Stunfisk": "Stunfisk de Galar",
    "Gourgeist Jumbo Variety": "Gourgeist (Variedad Jumbo)",
    "Gourgeist Large Variety": "Gourgeist (Variedad Grande)",
    "Gourgeist Small Variety": "Gourgeist (Variedad Pequeña)",
    "Hisuian Arcanine": "Arcanine de Hisui",
    "Hisuian Avalugg": "Avalugg de Hisui",
    "Hisuian Decidueye": "Decidueye de Hisui",
    "Hisuian Goodra": "Goodra de Hisui",
    "Hisuian Samurott": "Samurott de Hisui",
    "Hisuian Typhlosion": "Typhlosion de Hisui",
    "Hisuian Zoroark": "Zoroark de Hisui",
    "Lycanroc Dusk Form": "Lycanroc (Forma Crepuscular)",
    "Lycanroc Midnight Form": "Lycanroc (Forma Nocturna)",
    "Maushold Family of Four": "Maushold (Familia de Cuatro)",
    "Meowstic Female": "Meowstic (Hembra)",
    "Palafin Zero Form": "Palafin (Forma Zero)",
    "Paldean Tauros Aqua Breed": "Tauros de Paldea (Rebaño Acuático)",
    "Paldean Tauros Blaze Breed": "Tauros de Paldea (Rebaño Ígneo)",
    "Paldean Tauros Combat Breed": "Tauros de Paldea (Rebaño Combativo)",
    "Rotom Fan": "Rotom Ventilador",
    "Rotom Frost": "Rotom Frío",
    "Rotom Heat": "Rotom Calor",
    "Rotom Mow": "Rotom Corte",
    "Rotom Wash": "Rotom Lavado",
    "Vivillon Fancy Pattern": "Vivillon (Motivo Fantasía)",
}

# Slug de PokeAPI para las formas cuyo nombre mostrado no se convierte
# automáticamente (e.g. "Alolan Ninetales" -> "ninetales-alola").
SLUGS_POKEAPI = {
    "Aegislash Shield Forme": "aegislash-shield",
    "Alolan Ninetales": "ninetales-alola",
    "Alolan Raichu": "raichu-alola",
    "Fan Rotom": "rotom-fan",
    "Florges Red Flower": "florges-red",
    "Furfrou Natural Form": "furfrou-natural",
    "Galarian Slowbro": "slowbro-galar",
    "Galarian Slowking": "slowking-galar",
    "Galarian Stunfisk": "stunfisk-galar",
    "Gourgeist Jumbo Variety": "gourgeist-super",
    "Gourgeist Large Variety": "gourgeist-large",
    "Gourgeist Small Variety": "gourgeist-small",
    "Hisuian Arcanine": "arcanine-hisui",
    "Hisuian Avalugg": "avalugg-hisui",
    "Hisuian Decidueye": "decidueye-hisui",
    "Hisuian Goodra": "goodra-hisui",
    "Hisuian Samurott": "samurott-hisui",
    "Hisuian Typhlosion": "typhlosion-hisui",
    "Hisuian Zoroark": "zoroark-hisui",
    "Lycanroc Dusk Form": "lycanroc-dusk",
    "Lycanroc Midnight Form": "lycanroc-midnight",
    "Palafin Zero Form": "palafin-zero",
    "Paldean Tauros Aqua Breed": "tauros-paldea-aqua-breed",
    "Paldean Tauros Blaze Breed": "tauros-paldea-blaze-breed",
    "Paldean Tauros Combat Breed": "tauros-paldea-combat-breed",
    "Vivillon Fancy Pattern": "vivillon-fancy",
}

# Movimientos cuyo slug con apóstrofo no coincide con PokeAPI.
MOVIMIENTOS_SLUG = {
    "King's Shield": "kings-shield",
    "Forest's Curse": "forests-curse",
}

# Naturalezas EN -> ES (solo las que aparecen en la meta de championsbattledata).
NATURALEZAS_EN_ES = {
    "Adamant": "Firme", "Bold": "Osado", "Brave": "Audaz", "Calm": "Sereno",
    "Careful": "Cauteloso", "Gentle": "Amable", "Hardy": "Fuerte",
    "Hasty": "Activo", "Impish": "Brusco", "Jolly": "Alegre", "Lax": "Descuidado",
    "Lonely": "Huraño", "Mild": "Afable", "Modest": "Modesto",
    "Naive": "Ingenuo", "Naughty": "Imperfecto", "Quiet": "Manso",
    "Quirky": "Raro", "Rash": "Alocado", "Relaxed": "Flojo", "Serious": "Serio",
    "Sassy": "Fuerte", "Timid": "Miedoso",
}

# Objetos EN -> ES (los no mega evolucionan con la regla -ite -> -ita).
OBJETOS_EN_ES = {
    "Babiri Berry": "Baya Babiri", "Big Root": "Raíz Grande",
    "Black Belt": "Cinturón Negro", "Black Glasses": "Gafas Oscuras",
    "Bright Powder": "Polvo Brillante", "Charcoal": "Carbón",
    "Charti Berry": "Baya Charti", "Chesto Berry": "Baya Caqui",
    "Choice Scarf": "Pañuelo Elegido",
    "Chople Berry": "Baya Chople", "Coba Berry": "Baya Coba",
    "Colbur Berry": "Baya Colbur", "Damp Rock": "Roca Húmeda",
    "Dragon Fang": "Colmillo Dragón", "Expert Belt": "Cinto Pro",
    "Fairy Feather": "Pluma Hada", "Focus Band": "Cinta Focus",
    "Focus Sash": "Cinta Focus", "Haban Berry": "Baya Haban",
    "Hard Stone": "Piedra Dura", "Heat Rock": "Roca Caliente",
    "Icy Rock": "Roca Helada", "Iron Ball": "Bola de Hierro",
    "Kasib Berry": "Baya Kasib", "Kebia Berry": "Baya Kebia",
    "King's Rock": "Roca del Rey", "Leftovers": "Restos",
    "Life Orb": "Bola de Vida", "Light Ball": "Bola de Luz",
    "Light Clay": "Arcilla Especial", "Lum Berry": "Baya Zafiro",
    "Magnet": "Imán", "Mental Herb": "Hierba Mental",
    "Metal Coat": "Revestimiento Metálico", "Metronome": "Metrónomo",
    "Miracle Seed": "Semilla Milagro", "Muscle Band": "Banda Power",
    "Mystic Water": "Agua Mística", "Never-Melt Ice": "Hielo Eterno",
    "Occa Berry": "Baya Occa", "Oran Berry": "Baya Oran",
    "Passho Berry": "Baya Passho", "Payapa Berry": "Baya Payapa",
    "Poison Barb": "Púa Venenosa", "Quick Claw": "Garra Rápida",
    "Rindo Berry": "Baya Rindo", "Roseli Berry": "Baya Roseli",
    "Scope Lens": "Lente Focal", "Sharp Beak": "Pico Afilado",
    "Shed Shell": "Mudar Concha", "Shell Bell": "Campana Concha",
    "Shuca Berry": "Baya Shuca", "Silk Scarf": "Pañuelo Seda",
    "Silver Powder": "Polvo Plateado", "Sitrus Berry": "Baya Zidra",
    "Smooth Rock": "Roca Suave", "Soft Sand": "Arena Fina",
    "Spell Tag": "Hechizo", "Tanga Berry": "Baya Tanga",
    "Twisted Spoon": "Cuchara Torcida", "Wacan Berry": "Baya Wacan",
    "White Herb": "Hierba Blanca", "Wide Lens": "Lupa",
    "Wise Glasses": "Gafas Mañas", "Yache Berry": "Baya Yache",
    "Zoom Lens": "Zoom",
}


def objeto_es(nombre: str | None) -> str | None:
    """Traduce un objeto EN a ES (regla -ite -> -ita para mega piedras)."""
    if not nombre:
        return nombre
    if nombre in OBJETOS_EN_ES:
        return OBJETOS_EN_ES[nombre]
    if nombre.endswith("ite"):
        return nombre[:-3] + "ita"
    if nombre.endswith("ite X"):
        return nombre[:-5] + "ita X"
    if nombre.endswith("ite Y"):
        return nombre[:-5] + "ita Y"
    return nombre


def evs_es(cadena: str) -> str:
    """Traduce las siglas de EVs de una cadena (HP/Atk/... -> PS/Atq/...)."""
    for en, es in EVS_EN_ES.items():
        cadena = cadena.replace(en, es)
    return cadena

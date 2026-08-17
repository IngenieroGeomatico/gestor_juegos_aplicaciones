"""Importa datos reales de Pokémon Champions desde championsbattledata.com
y los traduce a español usando PokeAPI para los nombres.

Genera data/pokedex.json, data/movimientos.json y data/meta.json (ranking por
formato con sets recomendados) a partir de la API. Guarda en data/cache/ las
respuestas raw de ambas APIs para poder actualizar los ficheros sin volver a
golpear la red (borra caché con --sin-cache).

Ejemplo:
    uv run juegos/pokemon-champions/scripts/importar_datos.py
    uv run juegos/pokemon-champions/scripts/importar_datos.py --sin-cache
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
import urllib.request
from pathlib import Path

import data_store as ds

API_BASE = "https://championsbattledata.com"
UA = {"User-Agent": "gestor-juegos-bot/1.0"}
POKEAPI = "https://pokeapi.co/api/v2"
CACHE_DIR = ds.DATA_DIR / "cache"

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


def _objeto_es(nombre: str | None) -> str | None:
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


def _bajar(url: str, cache: str) -> dict:
    """Descarga JSON de una URL y lo cachea en data/cache/<cache>."""
    ruta = CACHE_DIR / cache
    if ruta.exists():
        with ruta.open(encoding="utf-8") as f:
            return json.load(f)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as resp:
        datos = json.loads(resp.read().decode())
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)
    time.sleep(0.1)
    return datos


def _nombre_es(names: list | None) -> str:
    """Nombre en español de la lista `names` de PokeAPI ("" si no existe)."""
    for n in names or []:
        if n.get("language", {}).get("name") == "es":
            return n.get("name", "")
    return ""


def _slug(nombre: str) -> str:
    """'Aura Sphere' -> 'aura-sphere'; 'King's Shield' -> 'kings-shield'."""
    slug = nombre.strip().lower()
    slug = slug.replace("'", "")
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def _traducir_especie(slug: str) -> dict:
    """Nombre en español, número y estatus legendario vía PokeAPI.

    Intenta /pokemon-species/{slug} y, si falla (formas regionales), /pokemon/{slug}
    resolviendo la especie base desde el enlace species.
    """
    for ruta in (f"pokemon-species/{slug}",
                 f"pokemon/{slug}",
                 f"pokemon-form/{slug}"):
        try:
            raw = _bajar(f"{POKEAPI}/{ruta}", f"pokeapi/{ruta}.json")
            if not isinstance(raw, dict) or "id" not in raw:
                continue
            if ruta.startswith("pokemon-species"):
                return {
                    "numero": raw.get("id"),
                    "nombre_es": _nombre_es(raw.get("names")) or raw.get("name", ""),
                    "legendario": bool(raw.get("is_legendary") or raw.get("is_mythical")),
                }
            # pokemon o pokemon-form: resolver la especie base.
            sp_url = raw.get("species", {}).get("url")
            if not sp_url:
                sp_url = raw.get("pokemon", {}).get("url")  # pokemon-form
            if not sp_url:
                continue
            sp_key = sp_url.split("/api/v2/")[-1]
            sp = _bajar(sp_url, f"pokeapi/{sp_key}")
            return {
                "numero": sp.get("id"),
                "nombre_es": _nombre_es(sp.get("names")) or raw.get("name", ""),
                "legendario": bool(sp.get("is_legendary") or sp.get("is_mythical")),
            }
        except Exception:
            continue
    return {}


def importar(sin_cache: bool) -> int:
    if sin_cache and CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print("Descargando índice de championsbattledata...")
    indice = _bajar(f"{API_BASE}/api/index", "champs/index.json")
    pokemon_list = indice["pokemon"]
    print(f"  {len(pokemon_list)} especies")

    pokedex = []
    movs_vistos: dict[str, None] = {}
    sin_traduccion = []
    vistos: set[str] = set()
    meta_por_formato: dict[str, list[dict]] = {"Doubles": [], "Singles": []}
    mapa_nombres_es: dict[str, str] = {}
    mapa_habilidades_es: dict[str, str] = {}

    for p in pokemon_list:
        nombre = p.get("name") or ""
        id_unico = p.get("showdownId") or p.get("slug") or nombre
        if id_unico in vistos:
            print(f"  (duplicado omitido: {nombre})")
            continue
        vistos.add(id_unico)
        resumen = p.get("summary", {}) or {}
        primario = resumen.get("primary", {}) or {}
        slug_poke = SLUGS_POKEAPI.get(nombre) or _slug(nombre)

        # Elegir la forma correcta del primary si la entrada tiene varias:
        # el index usa "primary" a veces con la forma base; tomamos los datos que
        # vienen en el propio primary (stats/tipos/habilidades) como hace la web.
        stats = {}
        for en, es in zip(STATS_CLAVES, STATS_ES):
            stats[es] = primario.get(en) or 0

        tipos = [TIPOS_EN_ES.get(t, t) for t in (primario.get("types") or resumen.get("types") or [])]

        habilidades = [h for h in (primario.get("abilities") or "").split("|") if h]

        movimientos = p.get("learnableMoveNames") or []
        for m in movimientos:
            movs_vistos[m] = None

        es_data = _traducir_especie(slug_poke)
        nombre_final = NOMBRES_FORMAS_ES.get(nombre) or es_data.get("nombre_es") or nombre

        habilidades_final = []
        for hab in habilidades:
            try:
                raw = _bajar(f"{POKEAPI}/ability/{_slug(hab)}",
                             f"pokeapi/ability/{_slug(hab)}.json")
                n = _nombre_es(raw.get("names")) if isinstance(raw, dict) else ""
                habilidades_final.append(n or hab)
            except Exception:
                habilidades_final.append(hab)

        if not es_data:
            sin_traduccion.append((nombre, slug_poke))

        pokedex.append({
            "numero": es_data.get("numero"),
            "nombre": nombre_final,
            "tipos": tipos,
            "stats": stats,
            "habilidades": habilidades_final,
            "legendario": es_data.get("legendario", False),
            "movimientos": movimientos,
        })

        mapa_nombres_es[nombre] = nombre_final
        for hab_en, hab_es in zip(habilidades, habilidades_final):
            mapa_habilidades_es[hab_en] = hab_es

        batalla = (resumen.get("battleSummary") or {}).get("Current") or {}
        for fmt in ("Doubles", "Singles"):
            info = batalla.get(fmt) or {}
            pos = info.get("position")
            if not pos:
                continue
            top = info.get("top") or {}
            val = info.get("values") or {}
            meta_por_formato[fmt].append({
                "posicion": pos,
                "nombre": nombre_final,
                "numero": es_data.get("numero"),
                "tipos": tipos,
                "movimientos": val.get("move") or [],
                "objeto": top.get("held_item", {}).get("name"),
                "naturaleza": top.get("stat_alignment", {}).get("name"),
                "habilidad": top.get("ability", {}).get("name"),
                "companeros": (val.get("teammate") or [])[:5],
            })

    print("Traduciendo movimientos a español vía PokeAPI...")
    movimientos = []
    sin_mov = []
    mapa_movs_es: dict[str, str] = {}
    for nombre_mv in movs_vistos:
        slug_mv = MOVIMIENTOS_SLUG.get(nombre_mv) or _slug(nombre_mv)
        try:
            raw = _bajar(f"{POKEAPI}/move/{slug_mv}", f"pokeapi/move/{slug_mv}.json")
            if not isinstance(raw, dict):
                raise ValueError
            tipo_en = raw.get("type", {}).get("name", "")
            nombre_es = _nombre_es(raw.get("names")) or nombre_mv
            mapa_movs_es[nombre_mv] = nombre_es
            movimientos.append({
                "nombre": nombre_es,
                "tipo": TIPOS_EN_ES.get(tipo_en, tipo_en),
                "categoria": CATEGORIAS.get(raw.get("damage_class", {}).get("name", ""), ""),
                "potencia": raw.get("power"),
                "precision": raw.get("accuracy"),
                "pp": raw.get("pp"),
            })
        except Exception:
            sin_mov.append(nombre_mv)
            movimientos.append({
                "nombre": nombre_mv,
                "tipo": "",
                "categoria": "",
                "potencia": None,
                "precision": None,
                "pp": None,
            })

    for e in pokedex:
        e["movimientos"] = [mapa_movs_es.get(m, m) for m in e.get("movimientos", [])]

    ds.guardar("pokedex", pokedex)
    ds.guardar("movimientos", movimientos)
    legendarios = sum(1 for e in pokedex if e["legendario"])
    print(f"Guardados pokedex.json ({len(pokedex)} especies, {legendarios} legendarias) "
          f"y movimientos.json ({len(movimientos)} movimientos)")

    # --- meta.json: ranking por formato con el set recomendado de cada especie ---
    for fmt, entradas in meta_por_formato.items():
        entradas.sort(key=lambda e: e["posicion"])
        for e in entradas:
            e["movimientos"] = [mapa_movs_es.get(m, m) for m in e["movimientos"]]
            e["objeto"] = _objeto_es(e["objeto"])
            e["naturaleza"] = NATURALEZAS_EN_ES.get(e["naturaleza"], e["naturaleza"])
            e["habilidad"] = mapa_habilidades_es.get(e["habilidad"], e["habilidad"])
            e["companeros"] = [mapa_nombres_es.get(c, c) for c in e["companeros"]]
    ds.guardar("meta", {
        "formato": {fmt: entradas for fmt, entradas in meta_por_formato.items()},
        "nota": "Ranking y sets recomendados por formato (Singles/Doubles) del meta actual.",
    })
    print(f"Guardado meta.json ({len(meta_por_formato['Doubles'])} en Doubles, "
          f"{len(meta_por_formato['Singles'])} en Singles)")
    if sin_traduccion:
        print(f"  {len(sin_traduccion)} especies sin traducción PokeAPI (nombre original):")
        for n, s in sin_traduccion:
            print(f"    - {n} ({s})")
    if sin_mov:
        print(f"  {len(sin_mov)} movimientos sin PokeAPI (nombre original): {sin_mov}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa datos reales de Pokémon Champions")
    parser.add_argument("--sin-cache", action="store_true", help="Borra la caché y redescarga todo")
    args = parser.parse_args()
    sys.exit(importar(args.sin_cache))


if __name__ == "__main__":
    main()
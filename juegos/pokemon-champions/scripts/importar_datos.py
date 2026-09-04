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
import shutil
import sys

import data_store as ds
import pc_api
from pc_api import (
    API_BASE,
    POKEAPI,
    bajar as _bajar,
    nombre_es as _nombre_es,
    slug as _slug,
    traducir_especie as _traducir_especie,
)
from pc_traducciones import (
    CATEGORIAS,
    MOVIMIENTOS_SLUG,
    NATURALEZAS_EN_ES,
    NOMBRES_FORMAS_ES,
    SLUGS_POKEAPI,
    STATS_CLAVES,
    STATS_ES,
    TIPOS_EN_ES,
    evs_es as _evs_es,
    objeto_es as _objeto_es,
)

CACHE_DIR = ds.DATA_DIR / "cache"


def importar(sin_cache: bool) -> int:
    if sin_cache and CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    pc_api.configurar_cache(CACHE_DIR)

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
                "evs": (val.get("stat_points") or [])[:2],
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
            e["evs"] = [_evs_es(ev) for ev in e.get("evs", [])]
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
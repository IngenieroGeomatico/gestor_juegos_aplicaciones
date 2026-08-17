"""Check de cobertura de tipos para un equipo de Pokémon Champions.

Analiza un equipo (de data/equipos.json o pasado por CLI) y muestra:
  - cobertura ofensiva (qué tipos golpea super-efectivamente cada miembro)
  - debilidades/resistencias defensivas agregadas del equipo
  - recomendaciones de cobertura

Ejemplos:
    uv run juegos/pokemon-champions/scripts/cobertura_tipos.py --equipo "Mi equipo"
    uv run juegos/pokemon-champions/scripts/cobertura_tipos.py --pokemon Groudon --pokemon Rayquaza
"""

from __future__ import annotations

import argparse
import sys

import data_store as ds

TIPOS_ORDEN = [
    "Normal", "Fuego", "Agua", "Eléctrico", "Hierba", "Hielo", "Lucha", "Veneno",
    "Tierra", "Volador", "Psíquico", "Bicho", "Roca", "Fantasma", "Dragón",
    "Siniestro", "Acero", "Hada",
]


def _tipos_ataque(especie: dict) -> list[str]:
    """Tipos ofensivos del miembro: STAB + tipos de sus movimientos si hay datos."""
    tipos = list(especie.get("tipos", []))
    for mov in ds.movimientos():
        if mov.get("nombre") in especie.get("movimientos", []):
            if mov.get("categoria") != "Estado" and mov.get("tipo") not in tipos:
                tipos.append(mov["tipo"])
    return tipos


def _resolver_especies(nombres: list[str]) -> tuple[list[dict], list[str]]:
    especies: list[dict] = []
    errores: list[str] = []
    for nombre in nombres:
        e = ds.buscar_especie(nombre)
        if e is None:
            errores.append(f"'{nombre}' no está en data/pokedex.json")
        else:
            especies.append(e)
    return especies, errores


def analizar(especies: list[dict]) -> None:
    print(f"\n=== Cobertura del equipo ({len(especies)} miembros) ===\n")

    # --- Ofensiva ---
    cubre: dict[str, int] = {}
    for e in especies:
        for tipo_at in _tipos_ataque(e):
            for tipo_obj in TIPOS_ORDEN:
                if ds.efectividad_total(tipo_at, [tipo_obj]) >= 2.0:
                    cubre[tipo_obj] = cubre.get(tipo_obj, 0) + 1
    sin_cubrir = [t for t in TIPOS_ORDEN if t not in cubre]
    print("Cobertura ofensiva (tipos golpeados super-efectivamente):")
    if not cubre:
        print("  (sin datos de tipos/movimientos para calcular)")
    else:
        print("  " + ", ".join(f"{t}: {c}x" for t, c in sorted(cubre.items(), key=lambda kv: -kv[1])))
        if sin_cubrir:
            print(f"  SIN CUBRIR: {', '.join(sin_cubrir)}")

    # --- Defensiva ---
    debil: dict[str, list[str]] = {}
    resist: dict[str, int] = {}
    inmune: dict[str, list[str]] = {}
    for e in especies:
        for tipo_at in TIPOS_ORDEN:
            mult = ds.efectividad_total(tipo_at, e.get("tipos", []))
            if mult >= 2.0:
                debil.setdefault(tipo_at, []).append(e["nombre"])
            elif mult == 0.5:
                resist[tipo_at] = resist.get(tipo_at, 0) + 1
            elif mult == 0.0:
                inmune.setdefault(tipo_at, []).append(e["nombre"])
    if debil:
        print("\nDebilidades defensivas (golpes super-efectivos recibidos):")
        for t, miembros in sorted(debil.items(), key=lambda kv: -len(kv[1])):
            print(f"  {t}: {len(miembros)} miembro(s) — {', '.join(miembros)}")
    if resist or inmune:
        print("\nResistencias/inmunidades:")
        if resist:
            print(f"  Resiste: {', '.join(f'{t} ({c})' for t, c in sorted(resist.items(), key=lambda kv: -kv[1]))}")
        if inmune:
            lista = ", ".join(f"{t} ({', '.join(m)})" for t, m in inmune.items())
            print(f"  Inmune: {lista}")

    # --- Recomendaciones ---
    if sin_cubrir:
        print(f"\nRecomendación: añade cobertura ofensiva para {', '.join(sin_cubrir[:3])}.")
    criticas = [t for t, m in debil.items() if len(m) >= 3]
    if criticas:
        print(f"Atención: {len(especies)}+ miembros comparten debilidad a {', '.join(criticas)}.")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Analiza la cobertura de tipos de un equipo")
    parser.add_argument("--pokemon", action="append", default=[], help="Nombre de un miembro (repetible)")
    parser.add_argument("--equipo", default=None, help="Nombre del equipo guardado en data/equipos.json")
    args = parser.parse_args()

    nombres: list[str] = []
    if args.equipo:
        equipos = ds.cargar("equipos")
        equipo = next((e for e in equipos if e.get("nombre") == args.equipo), None)
        if equipo is None:
            print(f"Error: no existe el equipo '{args.equipo}' en data/equipos.json")
            return 1
        nombres = [m.get("especie") for m in equipo.get("pokemon", [])]
    if args.pokemon:
        nombres += args.pokemon

    if not nombres:
        print("Indica miembros con --pokemon o un equipo con --equipo")
        return 1

    especies, errores = _resolver_especies(nombres)
    if errores:
        for e in errores:
            print(f"  ✗ {e}")
        return 1
    if len(especies) > 6:
        print("Error: un equipo competitivo tiene 6 Pokémon como máximo")
        return 1
    analizar(especies)
    return 0


if __name__ == "__main__":
    sys.exit(main())
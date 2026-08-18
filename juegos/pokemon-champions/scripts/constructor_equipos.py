"""Constructor de equipos para Pokémon Champions.

Construye un equipo de hasta 6 Pokémon, valida que existan en la pokedex, evita
duplicados, lo guarda en data/equipos.json y muestra su cobertura.

Ejemplos:
    uv run juegos/pokemon-champions/scripts/constructor_equipos.py --pokemon Groudon --pokemon Rayquaza --nombre "Equipo legendario"
    uv run juegos/pokemon-champions/scripts/constructor_equipos.py --auto --nombre "Autobot"
"""

from __future__ import annotations

import argparse
import random
import sys

import cobertura_tipos
import data_store as ds


def _elegir_auto() -> list[str]:
    pokedex = ds.pokedex()
    if not pokedex:
        print("Error: data/pokedex.json está vacío. Añade especies primero.")
        sys.exit(1)
    legendarios = [e["nombre"] for e in pokedex if e.get("legendario")]
    candidatos = legendarios or [e["nombre"] for e in pokedex]
    random.shuffle(candidatos)
    return candidatos[:6]


def main() -> None:
    parser = argparse.ArgumentParser(description="Construye un equipo competitivo")
    parser.add_argument("--pokemon", action="append", default=[], help="Nombre de un miembro (repetible)")
    parser.add_argument("--auto", action="store_true", help="Elegir 6 al azar (prioriza legendarios)")
    parser.add_argument("--nombre", required=True, help="Nombre del equipo")
    args = parser.parse_args()

    nombres = args.pokemon if args.pokemon else (_elegir_auto() if args.auto else [])
    if not nombres:
        print("Indica miembros con --pokemon (repetible) o usa --auto")
        return sys.exit(1)
    if len(nombres) > 6:
        print("Error: un equipo competitivo tiene 6 Pokémon como máximo")
        return sys.exit(1)

    especies, errores = ds.resolver_especies(nombres)
    if errores:
        for e in errores:
            print(f"  ✗ {e}")
        return sys.exit(1)

    equipo = {
        "nombre": args.nombre,
        "pokemon": [{"especie": e["nombre"], "tipos": e.get("tipos", []), "rol": "por definir"} for e in especies],
    }
    equipos = ds.cargar("equipos")
    equipos = [e for e in equipos if e.get("nombre") != args.nombre]
    equipos.append(equipo)
    ds.guardar("equipos", equipos)
    print(f"Equipo '{args.nombre}' guardado en data/equipos.json")
    cobertura_tipos.analizar(especies)
    return 0


if __name__ == "__main__":
    sys.exit(main())
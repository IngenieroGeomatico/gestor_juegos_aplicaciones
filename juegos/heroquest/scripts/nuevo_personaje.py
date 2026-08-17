"""Añade un nuevo héroe/personaje a HeroQuest."""

from __future__ import annotations

import argparse
import sys

import data_store


def main() -> None:
    parser = argparse.ArgumentParser(description="Añade un nuevo personaje jugable")
    parser.add_argument("--nombre", required=True, help="Nombre del personaje")
    parser.add_argument("--clase", required=True, help="Clase (Bárbaro, Mago, Ranger, ...)")
    parser.add_argument("--ataque", type=int, required=True, help="Dados de ataque")
    parser.add_argument("--defensa", type=int, required=True, help="Dados de defensa")
    parser.add_argument("--cuerpo", type=int, required=True, help="Puntos de cuerpo")
    parser.add_argument("--mente", type=int, required=True, help="Puntos de mente")
    parser.add_argument("--movimiento", type=int, default=2, help="Movimiento en casillas")
    parser.add_argument("--descripcion", default="", help="Descripción opcional")

    args = parser.parse_args()
    entrada = {
        "nombre": args.nombre,
        "clase": args.clase,
        "ataque": args.ataque,
        "defensa": args.defensa,
        "cuerpo": args.cuerpo,
        "mente": args.mente,
        "movimiento": args.movimiento,
        "descripcion": args.descripcion,
    }
    try:
        data_store.añadir("personajes", entrada)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    print(f"Añadido '{args.nombre}' a personajes.json")


if __name__ == "__main__":
    main()
"""Añade una nueva arma, armadura o poción a HeroQuest."""

from __future__ import annotations

import argparse
import sys

import data_store


def main() -> None:
    parser = argparse.ArgumentParser(description="Añade una nueva arma/armadura/poción")
    parser.add_argument("--nombre", required=True, help="Nombre del arma")
    parser.add_argument(
        "--tipo",
        required=True,
        choices=("Arma cuerpo a cuerpo", "Arma a distancia", "Armadura", "Poción"),
        help="Categoría del arma",
    )
    parser.add_argument("--ataque", type=int, default=0, help="Dados de ataque que otorga")
    parser.add_argument("--defensa", type=int, default=0, help="Dados de defensa que otorga")
    parser.add_argument("--coste", type=int, required=True, help="Coste en monedas de oro")
    parser.add_argument("--descripcion", default="", help="Descripción opcional")

    args = parser.parse_args()
    entrada = {
        "nombre": args.nombre,
        "tipo": args.tipo,
        "ataque": args.ataque,
        "defensa": args.defensa,
        "coste": args.coste,
        "descripcion": args.descripcion,
    }
    try:
        data_store.añadir("armas", entrada)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    print(f"Añadida '{args.nombre}' a armas.json")


if __name__ == "__main__":
    main()
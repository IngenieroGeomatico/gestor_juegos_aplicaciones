"""Lista el contenido de los datos de HeroQuest."""

from __future__ import annotations

import argparse

import data_store


def main() -> None:
    parser = argparse.ArgumentParser(description="Lista el contenido de HeroQuest")
    parser.add_argument(
        "--tipo",
        choices=data_store.TIPOS,
        default=None,
        help="Tipo de dato a listar (por defecto, todos)",
    )
    args = parser.parse_args()

    tipos = [args.tipo] if args.tipo else data_store.TIPOS
    for tipo in tipos:
        data_store.listar(tipo)


if __name__ == "__main__":
    main()
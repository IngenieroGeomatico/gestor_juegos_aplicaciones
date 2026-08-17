"""Elimina una entrada de HeroQuest por nombre."""

from __future__ import annotations

import argparse
import sys

import data_store


def main() -> None:
    parser = argparse.ArgumentParser(description="Elimina una entrada por nombre")
    parser.add_argument("--tipo", required=True, choices=data_store.TIPOS, help="Tipo de dato")
    parser.add_argument("--nombre", required=True, help="Nombre de la entrada a eliminar")

    args = parser.parse_args()
    if not data_store.eliminar(args.tipo, args.nombre):
        print(f"No se encontró '{args.nombre}' en {args.tipo}.json")
        sys.exit(1)
    print(f"Eliminado '{args.nombre}' de {args.tipo}.json")


if __name__ == "__main__":
    main()
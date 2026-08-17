"""Añade una nueva carta (personaje, arma, armadura, poción, monstruo o hechizo) a HeroQuest."""

from __future__ import annotations

import argparse
import sys

import data_store

TIPOS_CARTA = ("personaje", "arma", "armadura", "pocion", "monstruo", "hechizo")


def _anadir_y_validar(tipo: str, entrada: dict) -> None:
    try:
        data_store.añadir(tipo, entrada)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    print(f"Añadido '{entrada['nombre']}' a {tipo}.json")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Añade una nueva carta de personaje, arma, armadura, poción, "
        "monstruo o hechizo a HeroQuest",
    )
    parser.add_argument(
        "--tipo",
        required=True,
        choices=TIPOS_CARTA,
        help="Tipo de carta a crear",
    )
    parser.add_argument("--nombre", required=True, help="Nombre de la carta")
    parser.add_argument("--clase", help="Clase del personaje (Bárbaro, Mago, Ranger, ...)")
    parser.add_argument("--ataque", type=int, default=0, help="Dados de ataque")
    parser.add_argument("--defensa", type=int, default=0, help="Dados de defensa")
    parser.add_argument("--cuerpo", type=int, help="Puntos de cuerpo")
    parser.add_argument("--mente", type=int, help="Puntos de mente")
    parser.add_argument("--movimiento", type=int, default=2, help="Movimiento en casillas")
    parser.add_argument("--coste", type=int, help="Coste en monedas de oro")
    parser.add_argument("--escuela", help="Escuela del hechizo (Mago o Hechicero)")
    parser.add_argument("--coste_mente", type=int, help="Coste en puntos de mente del hechizo")
    parser.add_argument("--descripcion", default="", help="Descripción opcional")

    args = parser.parse_args()

    if args.tipo == "personaje":
        if args.clase is None or args.cuerpo is None or args.mente is None:
            parser.error("personaje requiere --clase, --cuerpo y --mente")
        _anadir_y_validar(
            "personajes",
            {
                "nombre": args.nombre,
                "clase": args.clase,
                "ataque": args.ataque,
                "defensa": args.defensa,
                "cuerpo": args.cuerpo,
                "mente": args.mente,
                "movimiento": args.movimiento,
                "descripcion": args.descripcion,
            },
        )
    elif args.tipo == "arma":
        if args.coste is None:
            parser.error("arma requiere --coste")
        _anadir_y_validar(
            "armas",
            {
                "nombre": args.nombre,
                "tipo": "Arma cuerpo a cuerpo",
                "ataque": args.ataque,
                "defensa": args.defensa,
                "coste": args.coste,
                "descripcion": args.descripcion,
            },
        )
    elif args.tipo == "armadura":
        if args.coste is None:
            parser.error("armadura requiere --coste")
        _anadir_y_validar(
            "armas",
            {
                "nombre": args.nombre,
                "tipo": "Armadura",
                "ataque": 0,
                "defensa": args.defensa,
                "coste": args.coste,
                "descripcion": args.descripcion,
            },
        )
    elif args.tipo == "pocion":
        if args.coste is None:
            parser.error("pocion requiere --coste")
        _anadir_y_validar(
            "armas",
            {
                "nombre": args.nombre,
                "tipo": "Poción",
                "ataque": 0,
                "defensa": 0,
                "coste": args.coste,
                "descripcion": args.descripcion,
            },
        )
    elif args.tipo == "monstruo":
        if args.cuerpo is None or args.mente is None:
            parser.error("monstruo requiere --cuerpo y --mente")
        _anadir_y_validar(
            "monstruos",
            {
                "nombre": args.nombre,
                "ataque": args.ataque,
                "defensa": args.defensa,
                "cuerpo": args.cuerpo,
                "mente": args.mente,
                "movimiento": args.movimiento,
                "descripcion": args.descripcion,
            },
        )
    elif args.tipo == "hechizo":
        if args.escuela is None or args.coste_mente is None:
            parser.error("hechizo requiere --escuela y --coste_mente")
        _anadir_y_validar(
            "hechizos",
            {
                "nombre": args.nombre,
                "escuela": args.escuela,
                "coste_mente": args.coste_mente,
                "descripcion": args.descripcion,
            },
        )


if __name__ == "__main__":
    main()
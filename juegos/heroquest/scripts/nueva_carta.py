"""Añade una nueva carta a HeroQuest (personaje, arma, armadura, poción,
monstruo o hechizo).

Este script es un orquestador: no conoce los campos de cada tipo de carta. Cada
tipo declara sus datos en `tipos_carta_datos.py` (campos, validación, cómo se
construye la entrada). Aquí solo se elige el tipo, se construye el CLI a partir
de sus campos y se guarda.

Ejemplos:
    uv run juegos/heroquest/scripts/nueva_carta.py --tipo hechizo --nombre "Bola de fuego" \\
        --escuela Mago --coste_mente 2 --descripcion "Causa 1 punto de daño"
    uv run juegos/heroquest/scripts/nueva_carta.py --tipo arma --nombre "Espada" --ataque 3 --coste 200
"""

from __future__ import annotations

import argparse
import sys

import data_store
import tipos_carta_datos


def _construir_parser() -> argparse.ArgumentParser:
    """Construye el CLI a partir de la unión de campos de todos los tipos.

    Todos los campos van como opcionales en argparse (se validan después según
    el tipo elegido), de modo que un mismo flag sirva para varios tipos.
    """
    parser = argparse.ArgumentParser(
        description="Añade una nueva carta (personaje, arma, armadura, poción, "
        "monstruo o hechizo) a HeroQuest",
    )
    parser.add_argument(
        "--tipo",
        required=True,
        choices=list(tipos_carta_datos.TIPOS),
        help="Tipo de carta a crear",
    )

    # Reunir todos los campos de todos los tipos, sin duplicar por nombre.
    vistos: dict[str, tipos_carta_datos.Campo] = {}
    for tipo in tipos_carta_datos.TIPOS.values():
        for campo in tipo.campos:
            vistos.setdefault(campo.nombre, campo)

    for campo in vistos.values():
        kwargs: dict = {"help": campo.ayuda}
        if campo.tipo is int:
            kwargs["type"] = int
        parser.add_argument(f"--{campo.nombre}", **kwargs)
    return parser


def main() -> None:
    parser = _construir_parser()
    args = parser.parse_args()

    tipo = tipos_carta_datos.obtener(args.tipo)
    if tipo is None:  # argparse ya lo restringe con choices; defensivo
        parser.error(f"Tipo '{args.tipo}' no válido")

    entrada = tipo.construir_entrada(vars(args))

    errores = tipo.validar(entrada)
    if errores:
        for e in errores:
            print(f"Error: {e}")
        sys.exit(1)

    try:
        data_store.añadir(tipo.fichero, entrada)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    print(f"Añadido '{entrada['nombre']}' a {tipo.fichero}.json")


if __name__ == "__main__":
    main()

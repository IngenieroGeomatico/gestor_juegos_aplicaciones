"""Añade una nueva misión a HeroQuest, montable en un tablero del juego.

Las salas se pasan desde un fichero JSON cuya raíz es una lista con el esquema:

    [
      {
        "numero": 1,
        "nombre": "La Antesala",
        "descripcion": "...",
        "monstruos": [{ "nombre": "Trasgo", "x": 1, "y": 2 }],
        "tesoros": [{ "nombre": "Poción de curación", "x": 3, "y": 1 }]
      }
    ]

Coordenadas globales de la cuadrícula (columna 1-26, fila 1-19 del tablero "original").
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import data_store
import tablero


def _punto(texto: str, contexto: str) -> dict:
    partes = texto.replace(" ", "").split(",")
    if len(partes) != 2:
        print(f"Error: {contexto} '{texto}' debe tener el formato X,Y")
        sys.exit(1)
    try:
        return {"x": int(partes[0]), "y": int(partes[1])}
    except ValueError:
        print(f"Error: {contexto} '{texto}' debe tener coordenadas enteras")
        sys.exit(1)


def _leer_habitaciones(ruta: str | None) -> list[dict]:
    if not ruta:
        return []
    fichero = Path(ruta)
    if not fichero.exists():
        print(f"Error: no existe el fichero '{ruta}'")
        sys.exit(1)
    with fichero.open(encoding="utf-8") as f:
        habitaciones = json.load(f)
    if not isinstance(habitaciones, list):
        print("Error: el fichero de habitaciones debe contener una lista")
        sys.exit(1)
    return habitaciones


def _validar(tablero_id: str, entrada: list[dict], puertas: list[dict], salas: list[dict]) -> None:
    t = tablero.cargar_tablero(tablero_id)
    if not t["salas"]:
        print(f"Error: el tablero '{tablero_id}' aún no está modelado ({t['nota']})")
        sys.exit(1)
    errores: list[str] = []
    for p in entrada:
        errores += tablero.punto_valido(t, p, "entrada_heroes")
    for p in puertas:
        errores += tablero.punto_valido(t, p, "puerta")
    for sala in salas:
        errores += tablero.sala_pertenece(t, sala)
    if errores:
        for e in errores:
            print(f"  ✗ {e} (tablero {tablero_id})")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Añade una nueva misión montable en tablero")
    parser.add_argument("--nombre", required=True, help="Nombre de la misión")
    parser.add_argument("--tablero", default="original", help="ID del tablero (original, cara-b)")
    parser.add_argument("--nivel", type=int, default=1, help="Nivel de dificultad")
    parser.add_argument("--introduccion", default="", help="Texto de introducción")
    parser.add_argument("--objetivo", required=True, help="Objetivo de la misión")
    parser.add_argument("--recompensa", default="", help="Recompensa al completarla")
    parser.add_argument("--entrada", action="append", default=[], metavar="X,Y",
                        help="Casilla de entrada de los héroes (repetible)")
    parser.add_argument("--puerta", action="append", default=[], metavar="X,Y",
                        help="Casilla de puerta (repetible)")
    parser.add_argument("--habitaciones", default=None,
                        help="Ruta a un JSON con la lista de salas de la misión")

    args = parser.parse_args()
    entrada = [_punto(c, "entrada") for c in args.entrada]
    puertas = [_punto(c, "puerta") for c in args.puerta]
    salas = _leer_habitaciones(args.habitaciones)
    _validar(args.tablero, entrada, puertas, salas)

    mision = {
        "nombre": args.nombre,
        "tablero": args.tablero,
        "nivel": args.nivel,
        "introduccion": args.introduccion,
        "objetivo": args.objetivo,
        "recompensa": args.recompensa,
        "entrada_heroes": entrada,
        "puertas": puertas,
        "salas": salas,
    }
    try:
        data_store.añadir("misiones", mision)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    print(f"Añadida misión '{args.nombre}' a misiones.json (tablero {args.tablero}).")


if __name__ == "__main__":
    main()
"""Gestión de los tableros de HeroQuest: imprimir el mapa y validar misiones.

Ejemplos:
    uv run juegos/heroquest/scripts/tablero.py ver --tablero original
    uv run juegos/heroquest/scripts/tablero.py validar
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_ETIQUETA_SALA = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def cargar_tablero(tablero_id: str) -> dict:
    ruta = DATA_DIR / "tableros.json"
    with ruta.open(encoding="utf-8") as f:
        tableros = json.load(f)
    for t in tableros:
        if t["id"] == tablero_id:
            return t
    print(f"Error: no existe el tablero '{tablero_id}'")
    sys.exit(1)


def sala_en(tablero: dict, x: int, y: int) -> int | None:
    """Devuelve el número de sala que contiene (x, y) o None si es pasillo."""
    for sala in tablero["salas"]:
        for rect in sala["rects"]:
            rx = rect["x"]
            ry = rect["y"]
            if rx <= x < rx + rect["ancho"] and ry <= y < ry + rect["alto"]:
                return sala["numero"]
    return None


def es_no_jugable(tablero: dict, x: int, y: int) -> bool:
    """True si la casilla (x, y) está marcada como roca dura / no jugable."""
    return [x, y] in tablero.get("no_jugables", [])


def pinta(tablero: dict) -> str:
    """Dibuja el tablero como cuadrícula ASCII: números de sala y '.' para pasillos."""
    lineas = []
    cabecera = "    " + "".join(str(c % 10) for c in range(1, tablero["columnas"] + 1))
    lineas.append(cabecera)
    for y in range(1, tablero["filas"] + 1):
        fila = f"{y:>3} "
        for x in range(1, tablero["columnas"] + 1):
            if es_no_jugable(tablero, x, y):
                fila += "#"
                continue
            num = sala_en(tablero, x, y)
            if num is None:
                fila += "."
            else:
                fila += _ETIQUETA_SALA[num % len(_ETIQUETA_SALA)]
        lineas.append(fila)
    return "\n".join(lineas)


def punto_valido(tablero: dict, p: dict, contexto: str) -> list[str]:
    """Comprueba que un punto {x, y} caiga dentro del tablero y sea jugable.
    Devuelve errores."""
    x, y = p.get("x"), p.get("y")
    if not isinstance(x, int) or not isinstance(y, int):
        return [f"{contexto}: coordenadas no enteras en {p}"]
    if not (1 <= x <= tablero["columnas"] and 1 <= y <= tablero["filas"]):
        return [f"{contexto}: ({x},{y}) fuera del tablero"]
    if es_no_jugable(tablero, x, y):
        return [f"{contexto}: ({x},{y}) cae en roca dura (casilla no jugable)"]
    return []


def _punto_en_sala(sala: dict, x: int, y: int) -> bool:
    for rect in sala["rects"]:
        if rect["x"] <= x < rect["x"] + rect["ancho"] and rect["y"] <= y < rect["y"] + rect["alto"]:
            return True
    return False


def sala_pertenece(tablero: dict, sala: dict) -> list[str]:
    """Valida que una sala de misión exista en el tablero y que sus
    monstruos/tesoros caigan dentro de ella. Devuelve la lista de errores."""
    errores: list[str] = []
    numero = sala.get("numero")
    sala_data = next((s for s in tablero["salas"] if s["numero"] == numero), None)
    if sala_data is None:
        return [f"sala {numero}: no existe en el tablero"]
    for obstaculo in ("monstruos", "tesoros", "trampas", "marcadores"):
        for item in sala.get(obstaculo, []):
            nombre = item.get("nombre", "?")
            contexto = f"sala {numero}.{obstaculo} '{nombre}'"
            errores += punto_valido(tablero, item, contexto)
            x, y = item.get("x"), item.get("y")
            if isinstance(x, int) and isinstance(y, int) and not _punto_en_sala(sala_data, x, y):
                errores.append(f"{contexto}: ({x},{y}) no cae dentro de la sala {numero}")
    return errores


def validar_misiones() -> int:
    """Valida que todas las misiones sean montables en su tablero."""
    with (DATA_DIR / "misiones.json").open(encoding="utf-8") as f:
        misiones = json.load(f)
    errores: list[str] = []
    for mision in misiones:
        tablero = cargar_tablero(mision["tablero"])
        if not tablero["salas"]:
            errores.append(f"misión '{mision['nombre']}': el tablero '{tablero['id']}' aún no está modelado")
            continue
        for t in mision.get("entrada_heroes", []):
            errores += punto_valido(tablero, t, f"misión '{mision['nombre']}' entrada_heroes")
        for p in mision.get("puertas", []):
            errores += punto_valido(tablero, p, f"misión '{mision['nombre']}' puerta")
        for p in mision.get("puertas_secretas", []):
            errores += punto_valido(tablero, p, f"misión '{mision['nombre']}' puerta secreta")
        for sala in mision.get("salas", []):
            errores += sala_pertenece(tablero, sala)

    if errores:
        for e in errores:
            print(f"  ✗ {e}")
        return 1
    print(f"OK: {len(misiones)} misiones montables en sus tableros.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Utilidades de tableros de HeroQuest")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_ver = sub.add_parser("ver", help="Imprime el mapa ASCII de un tablero")
    p_ver.add_argument("--tablero", required=True, help="ID del tablero (original, cara-b)")

    sub.add_parser("validar", help="Valida que todas las misiones caben en su tablero")

    args = parser.parse_args()
    if args.comando == "ver":
        tablero = cargar_tablero(args.tablero)
        if not tablero["salas"]:
            print(f"Tablero '{args.tablero}' aún sin modelar ({tablero['nota']})")
            return
        print(pinta(tablero))
        print(f"\nTablero {tablero['id']} · {tablero['columnas']}x{tablero['filas']} · {tablero['nota']}")
    elif args.comando == "validar":
        sys.exit(validar_misiones())


if __name__ == "__main__":
    main()
"""Construye data/tableros.json a partir de ficheros de trazado .rooms.txt.

Cada tablero se traza en un fichero de texto legible `data/<id>.rooms.txt` leyendo
la rejilla numerada que produce `tablero_calibrar.py`. El formato por línea es:

    numero_sala, x1, y1, x2, y2

con coordenadas **1-indexadas** e **inclusivas** en la cuadrícula apaisada
(columna x de 1..columnas, fila y de 1..filas). Una sala en L o compuesta se
declara con **varias líneas del mismo numero_sala**; cada línea es un rectángulo.
Las líneas en blanco y las que empiezan por '#' se ignoran.

    # sala central en cruz (dos rects, mismo numero)
    11, 12, 8, 15, 12
    11, 13, 13, 14, 13

El resultado se mezcla en `data/tableros.json` respetando los metadatos
existentes de cada tablero (nombre, columnas, filas, nota) y sustituyendo solo
su lista `salas`. Convierte cada (x1,y1,x2,y2) a `{x, y, ancho, alto}` como usa
el resto de scripts (`tablero.py`, `mapa.py`, validación de misiones).

Ejemplos:
    uv run juegos/heroquest/scripts/tablero_construir.py --id original
    uv run juegos/heroquest/scripts/tablero_construir.py --todos
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TABLEROS_JSON = DATA_DIR / "tableros.json"


def _rect_desde_esquinas(x1: int, y1: int, x2: int, y2: int) -> dict:
    """Convierte (x1,y1,x2,y2) inclusivos a {x, y, ancho, alto}."""
    x_min, x_max = sorted((x1, x2))
    y_min, y_max = sorted((y1, y2))
    return {
        "x": x_min,
        "y": y_min,
        "ancho": x_max - x_min + 1,
        "alto": y_max - y_min + 1,
    }


def leer_rooms(ruta: Path) -> list[dict]:
    """Lee un .rooms.txt y devuelve la lista de salas [{numero, rects[]}]."""
    salas: dict[int, dict] = {}
    orden: list[int] = []
    for n_linea, cruda in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
        linea = cruda.split("#", 1)[0].strip()
        if not linea:
            continue
        partes = [p.strip() for p in linea.split(",")]
        if len(partes) != 5:
            raise ValueError(
                f"{ruta.name}:{n_linea}: se esperaban 5 valores "
                f"(numero, x1, y1, x2, y2), hay {len(partes)}: {cruda!r}"
            )
        try:
            numero, x1, y1, x2, y2 = (int(p) for p in partes)
        except ValueError as e:
            raise ValueError(f"{ruta.name}:{n_linea}: valores no enteros: {cruda!r}") from e
        if numero not in salas:
            salas[numero] = {"numero": numero, "rects": []}
            orden.append(numero)
        salas[numero]["rects"].append(_rect_desde_esquinas(x1, y1, x2, y2))
    return [salas[n] for n in orden]


def _validar_dentro(sala: dict, columnas: int, filas: int) -> list[str]:
    errores: list[str] = []
    for r in sala["rects"]:
        if r["x"] < 1 or r["y"] < 1:
            errores.append(f"sala {sala['numero']}: rect {r} empieza fuera (min 1,1)")
        if r["x"] + r["ancho"] - 1 > columnas or r["y"] + r["alto"] - 1 > filas:
            errores.append(
                f"sala {sala['numero']}: rect {r} se sale del tablero "
                f"{columnas}x{filas}"
            )
    return errores


def construir(ids: list[str]) -> None:
    tableros = json.loads(TABLEROS_JSON.read_text(encoding="utf-8"))
    por_id = {t["id"]: t for t in tableros}

    for tid in ids:
        if tid not in por_id:
            raise SystemExit(f"Tablero '{tid}' no existe en tableros.json")
        ruta = DATA_DIR / f"{tid}.rooms.txt"
        if not ruta.exists():
            raise SystemExit(f"Falta el fichero de trazado: {ruta}")

        tablero = por_id[tid]
        salas = leer_rooms(ruta)
        errores: list[str] = []
        for sala in salas:
            errores += _validar_dentro(sala, tablero["columnas"], tablero["filas"])
        if errores:
            for e in errores:
                print(f"  ✗ {e}")
            raise SystemExit(f"Trazado de '{tid}' inválido: {len(errores)} errores")

        tablero["salas"] = salas
        print(f"OK '{tid}': {len(salas)} salas cargadas desde {ruta.name}")

    TABLEROS_JSON.write_text(
        json.dumps(tableros, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Escrito {TABLEROS_JSON}")


def main() -> None:
    p = argparse.ArgumentParser(description="Construye tableros.json desde .rooms.txt")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--id", help="ID del tablero a reconstruir (original, cara-b)")
    g.add_argument("--todos", action="store_true", help="Reconstruye todos los .rooms.txt existentes")
    args = p.parse_args()

    if args.todos:
        ids = [f.name[: -len(".rooms.txt")] for f in DATA_DIR.glob("*.rooms.txt")]
        if not ids:
            raise SystemExit("No hay ficheros .rooms.txt en data/")
    else:
        ids = [args.id]
    construir(ids)


if __name__ == "__main__":
    main()

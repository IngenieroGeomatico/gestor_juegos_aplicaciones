"""Construye data/tableros.json a partir del SVG vectorial de un tablero.

El SVG es la **fuente de verdad** del tablero: cada sala (cámara) es un
`<rect>` o un `<path>` ortogonal dentro del grupo `<g id="rooms">`, en
coordenadas de la cuadrícula (con una transformación `scale(N)`). El viewBox
determina el tamaño del tablero en casillas. Todo lo no cubierto por una sala
es **pasillo** (implícito, como en el resto de scripts).

Ventajas frente al flujo foto → calibrar → `.rooms.txt` (`tablero_calibrar.py`
+ `tablero_construir.py`): sin perspectiva, sin trazado manual y reproducible.
El SVG es ligero (texto) y las salas ya vienen como rectángulos exactos.

Numeración (canónica, opción A): las salas se numeran 1..N en orden de lectura
row-major con tolerancia de banda (fila y luego columna de la esquina superior
-izquierda). Es determinista y estable frente a reordenaciones del XML.

Conversión de coordenadas: el SVG es 0-indexado; el repo es 1-indexado e
inclusivo de origen (`{x, y, ancho, alto}` cubre x..x+ancho-1, y..y+alto-1),
así que se suma 1 a cada origen.

Ejemplos:
    uv run juegos/heroquest/scripts/tablero_svg.py \
        --svg juegos/heroquest/sources/heroquest_board_original.svg --id original
    uv run juegos/heroquest/scripts/tablero_svg.py \
        --svg juegos/heroquest/sources/heroquest_board_back.svg --id cara-b
"""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TABLEROS_JSON = DATA_DIR / "tableros.json"

_SVG_NS = "{http://www.w3.org/2000/svg}"

# Tolerancia (en casillas) para agrupar salas en la misma "banda" horizontal al
# numerar: dos salas cuya esquina superior difiere menos que esto en Y se
# consideran de la misma fila y se ordenan por X.
_BANDA_Y = 2


def _local(tag: str) -> str:
    """Nombre de etiqueta sin el namespace SVG."""
    return tag[len(_SVG_NS):] if tag.startswith(_SVG_NS) else tag


def _escala_de(grupo: ET.Element) -> float:
    """Lee el factor de `transform="scale(N)"` del grupo de salas (1 si no hay)."""
    transform = grupo.get("transform", "")
    m = re.search(r"scale\(\s*([0-9.]+)", transform)
    return float(m.group(1)) if m else 1.0


def _viewbox_casillas(raiz: ET.Element, escala: float) -> tuple[int, int]:
    """Deduce (columnas, filas) del viewBox del SVG divididas por la escala."""
    vb = raiz.get("viewBox")
    if not vb:
        raise ValueError("El SVG no tiene viewBox; no puedo deducir el tamaño del tablero")
    _, _, ancho, alto = (float(v) for v in vb.replace(",", " ").split())
    return round(ancho / escala), round(alto / escala)


def _rects_de_path(d: str) -> list[tuple[float, float, float, float]]:
    """Descompone un `<path>` ortogonal (M, h/H, v/V, z) en rectángulos.

    Reconstruye el polígono como lista de vértices y lo trocea en franjas
    horizontales por cada par de coordenadas Y consecutivas: para cada franja,
    el interior es un rectángulo (los polígonos de las salas son ortogonales y
    simples). Devuelve rects como (x, y, ancho, alto) en coordenadas del SVG.
    """
    tokens = re.findall(r"[MmHhVvZzLl]|-?[0-9.]+", d)
    vertices: list[tuple[float, float]] = []
    x = y = 0.0
    i = 0
    comando = ""
    while i < len(tokens):
        t = tokens[i]
        if t.isalpha():
            comando = t
            i += 1
            if comando in ("Z", "z"):
                continue
        rel = comando.islower()
        c = comando.upper()
        if c == "M":
            nx, ny = float(tokens[i]), float(tokens[i + 1])
            x, y = (x + nx, y + ny) if rel else (nx, ny)
            i += 2
        elif c == "L":
            nx, ny = float(tokens[i]), float(tokens[i + 1])
            x, y = (x + nx, y + ny) if rel else (nx, ny)
            i += 2
        elif c == "H":
            nx = float(tokens[i])
            x = x + nx if rel else nx
            i += 1
        elif c == "V":
            ny = float(tokens[i])
            y = y + ny if rel else ny
            i += 1
        else:
            raise ValueError(f"Comando de path no soportado: {comando!r} en {d!r}")
        vertices.append((x, y))

    ys = sorted({vy for _, vy in vertices})
    rects: list[tuple[float, float, float, float]] = []
    for y0, y1 in zip(ys, ys[1:]):
        mitad = (y0 + y1) / 2
        # Bordes verticales que cruzan esta franja → tramos interiores por X.
        cruces = sorted(
            vx
            for (ax, ay), (bx, by) in zip(vertices, vertices[1:] + vertices[:1])
            if ax == bx and min(ay, by) <= mitad <= max(ay, by)
            for vx in (ax,)
        )
        for x0, x1 in zip(cruces[0::2], cruces[1::2]):
            rects.append((x0, y0, x1 - x0, y1 - y0))
    return rects


def _shapes_del_svg(ruta: Path) -> tuple[list[dict], int, int]:
    """Extrae las salas del SVG.

    Devuelve (shapes, columnas, filas) donde cada shape es
    {rects: [(x,y,ancho,alto)], color} en coordenadas del SVG ya sin escala.
    """
    raiz = ET.parse(ruta).getroot()
    grupo = next(
        (g for g in raiz.iter(f"{_SVG_NS}g") if g.get("id") == "rooms"),
        None,
    )
    if grupo is None:
        raise ValueError("El SVG no tiene un grupo <g id='rooms'>")

    escala = _escala_de(grupo)
    columnas, filas = _viewbox_casillas(raiz, escala)

    shapes: list[dict] = []
    for el in grupo:
        etiqueta = _local(el.tag)
        color = el.get("fill")
        if etiqueta == "rect":
            rects = [(
                float(el.get("x", 0)),
                float(el.get("y", 0)),
                float(el.get("width", 0)),
                float(el.get("height", 0)),
            )]
        elif etiqueta == "path":
            rects = _rects_de_path(el.get("d", ""))
        else:
            continue
        if rects:
            shapes.append({"rects": rects, "color": color})
    return shapes, columnas, filas


def _a_rect_repo(rect: tuple[float, float, float, float]) -> dict:
    """Convierte (x,y,ancho,alto) del SVG (0-indexado) al esquema del repo (1-indexado)."""
    x, y, ancho, alto = rect
    return {
        "x": round(x) + 1,
        "y": round(y) + 1,
        "ancho": round(ancho),
        "alto": round(alto),
    }


def _clave_orden(shape: dict) -> tuple[int, float]:
    """Clave de numeración canónica: banda-Y (fila) y luego X de la esquina sup-izq."""
    x_min = min(r[0] for r in shape["rects"])
    y_min = min(r[1] for r in shape["rects"])
    return (round(y_min / _BANDA_Y), x_min)


def _numerar(shapes: list[dict]) -> list[dict]:
    """Ordena las salas (row-major con banda) y les asigna numero 1..N."""
    ordenadas = sorted(shapes, key=_clave_orden)
    salas: list[dict] = []
    for numero, shape in enumerate(ordenadas, 1):
        sala = {"numero": numero, "rects": [_a_rect_repo(r) for r in shape["rects"]]}
        if shape.get("color"):
            sala["color"] = shape["color"]
        salas.append(sala)
    return salas


def _validar_dentro(sala: dict, columnas: int, filas: int) -> list[str]:
    errores: list[str] = []
    for r in sala["rects"]:
        if r["x"] < 1 or r["y"] < 1:
            errores.append(f"sala {sala['numero']}: rect {r} empieza fuera (min 1,1)")
        if r["x"] + r["ancho"] - 1 > columnas or r["y"] + r["alto"] - 1 > filas:
            errores.append(
                f"sala {sala['numero']}: rect {r} se sale del tablero {columnas}x{filas}"
            )
    return errores


def construir(svg: Path, tablero_id: str) -> None:
    if not svg.exists():
        raise SystemExit(f"No existe el SVG: {svg}")

    tableros = json.loads(TABLEROS_JSON.read_text(encoding="utf-8"))
    por_id = {t["id"]: t for t in tableros}
    if tablero_id not in por_id:
        raise SystemExit(f"Tablero '{tablero_id}' no existe en tableros.json")

    shapes, columnas, filas = _shapes_del_svg(svg)
    if not shapes:
        raise SystemExit(f"No se encontraron salas en {svg.name}")
    salas = _numerar(shapes)

    errores: list[str] = []
    for sala in salas:
        errores += _validar_dentro(sala, columnas, filas)
    if errores:
        for e in errores:
            print(f"  ✗ {e}")
        raise SystemExit(f"Salas de '{tablero_id}' inválidas: {len(errores)} errores")

    tablero = por_id[tablero_id]
    tablero["columnas"] = columnas
    tablero["filas"] = filas
    tablero["salas"] = salas
    tablero["nota"] = f"Generado desde {svg.name} (fuente vectorial). Las casillas no cubiertas por una sala son pasillo."

    TABLEROS_JSON.write_text(
        json.dumps(tableros, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"OK '{tablero_id}': {len(salas)} salas, {columnas}x{filas}, desde {svg.name}")
    print(f"Escrito {TABLEROS_JSON}")


def main() -> None:
    p = argparse.ArgumentParser(description="Construye tableros.json desde el SVG de un tablero")
    p.add_argument("--svg", required=True, help="Ruta del SVG del tablero")
    p.add_argument("--id", required=True, help="ID del tablero (original, cara-b)")
    args = p.parse_args()
    construir(Path(args.svg), args.id)


if __name__ == "__main__":
    main()
